#!/usr/bin/env python
import discord
import asyncio
import subprocess
import json
import logging
from time import sleep
from discord.ext import commands
from discord.ui import Button, View
from pytubefix import YouTube, Playlist, Search

logging.basicConfig(filename='/home/potts/ribbit.log',
                    filemode='w',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)

# Read token from file
with open('/home/potts/git/Ribbit/TOKEN.txt','r') as f:
    TOKEN = f.read()

# Setting command prefix and intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# Define a list for queueing videos as Global variable
queue = []

# Define a list of background tasks globally so they can be stopped if needed
bg_tasks = []

# Define Batch Size for Playlist loading
BATCH = 1
BATCH_WAIT = 5


async def search_yt(ctx, search):
    # Search YouTube using search string
    results =  [video for video in Search(search).videos]

    # Create a list of rows
    rows = []
    buttons = []
    for i, vid in enumerate(results[:5]):
        button = Button(label=f"{i + 1}.", style=discord.ButtonStyle.primary, custom_id=vid.watch_url)
        row = (f'{i + 1}.', f'{vid.title}', f'{vid.length/60:.2f} min')
        rows.append(row)
        buttons.append(button)

    # Define header and sep
    header = ['Result', 'Title', 'Length']

    # Calculate column widths
    col_widths = []
    for i in range(len(header)):
        # For each column, find the maximum length between the header and the rows
        try:
            max_len = max(len(header[i]), max(len(row[i]) for row in rows))
        except ValueError as e:
            ctx.followup.send(f'YouTube had no results for "{search}"... Sorry. Try again!')
            return
        col_widths.append(max_len)
        
    # Format the table
    header_row = " | ".join(header[i].ljust(col_widths[i]) for i in range(len(header)))
    formatted_rows = "\n".join(
        " | ".join(row[i].ljust(col_widths[i]) for i in range(len(header))) for row in rows
    )
    #logging.debug(formatted_rows)
    separator = "-" * (sum(col_widths) + len(header) * 3 - 1)

    # Create a view to hold the buttons
    view = View()
    for button in buttons:
        view.add_item(button)

    # Send a message with the buttons
    table = f"{header_row}\n{separator}\n{formatted_rows}"
    logging.debug(table)
    await ctx.followup.send(f"Click a button to play a video!\n```{table}```", view=view)

# Button interaction handler
@bot.event
async def on_interaction(interaction):
    logging.debug(interaction)
    if interaction.type == discord.InteractionType.component:
        # Get the URL from the button's custom_id
        url = interaction.data['custom_id']

        # Call the preload_songs function, passing the URL
        logging.debug(interaction.user)
        logging.debug(interaction.user.voice.channel)
        play_cmd = bot.tree.get_command('play')
        await play_cmd.callback(interaction, url)  # Pass the URL to the play function


async def preload_songs(ctx, youtube_url):
    logging.info(f'Preloading {youtube_url}.')
    processes = {}
    stdout = {}
    stderr = {}
    if 'playlist' in youtube_url:
        await ctx.response.send(f'Preloading Playlist. I will add these songs to the queue {BATCH} song at a time to a total queue size of {BATCH_WAIT}. Then I will wait for more queue space to add more songs.')
        pl = list(Playlist(youtube_url))
        logging.debug(pl)
        while pl:
            if len(queue) < BATCH_WAIT:
                batch = pl[:BATCH]  # take a batch from the playlist
                pl = pl[BATCH:]     # removed processed items from the playlist
                processes = {
                    i: await asyncio.create_subprocess_exec('python','/home/potts/git/Ribbit/preload.py', url, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for i, url in enumerate(batch)
                }
                logging.debug(processes)
                songs = []
                for i,v in processes.items():
                    stdout[i],stderr[i] = await processes[i].communicate()
                    if processes[i].returncode == 0:
                        songs.append(json.loads(stdout[i].decode())[0])
                await add_to_queue(ctx, songs)
            else:
                #logging.debug(f'At BATCH_WAIT limit! Current length of the queue is {len(queue)}.')
                await asyncio.sleep(60)
    else:
        message = f'Preloading song. Please wait.'
        if isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(message)
        else:
            await ctx.reply(message)
        logging.info(message)
        processes[0] = await asyncio.create_subprocess_exec('python', '/home/potts/git/Ribbit/preload.py', youtube_url, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout[0], stderr[0] = await processes[0].communicate()
        logging.debug(f'Preloaded output:\n{stdout[0].decode()}')
        logging.debug(f'Process Return Code: {processes[0].returncode}')
        if processes[0].returncode == 0:
            songs = json.loads(stdout[0].decode())
            await add_to_queue(ctx, songs)

async def add_to_queue(ctx, songs):
    for song in songs:
        title, video_url, length = song
        audio_source = discord.FFmpegPCMAudio(video_url, options='-vn', before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5')
        audio_source.read() # read the audio binary output (3-4 seconds), prevents audio from playing a little too fast in the beginning
        queue.append([title, audio_source, length])
    await ctx.channel.send(f'Adding {len(songs)} songs to the queue.')

@bot.event
async def on_ready():
    logging.info(f'We have logged in as {bot.user}')
    await bot.tree.sync() # sync commands

@bot.event
async def on_voice_state_update(member, before, after):
    voice_client = discord.utils.get(bot.voice_clients, guild=member.guild)
    if not voice_client:
        return

    # Check if the bot is still connected to voice Channel
    voice_channel = voice_client.channel

    # Check if there are any members left in the voice channel, excluding the bot itself
    if len(voice_channel.members) == 1 and voice_channel.members[0] == bot.user:
        await voice_client.disconnect()
        logging.debug(f"VC disconnected due to lack of members.")

@bot.tree.command(name="play", description='Play YouTube links. Or search for a song!')
async def play(ctx: discord.Interaction, youtube_url: str):
    # Check if Author is in  channel
    author = ctx.user
    try:
        voice_channel = author.voice.channel
    except AttributeError:
        logging.info(f'{author} you need to be in a voice channel before using me to play audio.')
        await ctx.channel.send(f'{author} you need to be in a voice channel before using me to play audio.')
        return

    # Check if YouTube link
    if 'https://' not in youtube_url:
        logging.debug(f'Play command Author: {author}, Channel: {voice_channel}, Search: "{youtube_url}"')
        await ctx.response.send_message(f'Searching YouTube for "{youtube_url}"')
        logging.info(f'Searching YouTube for "{youtube_url}"')

        # Search YouTube for videos
        await search_yt(ctx, youtube_url)
        return

    # Grab author voice channel and print it to log
    logging.debug(f'Play command Author: {author}, Channel: {voice_channel}, URL: {youtube_url}')

    #### Preload songs to queue ####
    proc = bot.loop.create_task(preload_songs(ctx, youtube_url))
    bg_tasks.append(proc)

    # Check if Bot is already in voice channel
    vc = ctx.guild.voice_client
    if not vc:
        while len(queue) == 0:
            await asyncio.sleep(1)
        vc = await voice_channel.connect()
        logging.info('Entering VC.')
    else:
        return

    await play_next(vc, ctx)

@bot.tree.command(name="pause", description='Pause YouTube playback.')
async def pause(ctx: discord.Interaction):
    vc = ctx.guild.voice_client
    if vc.is_playing():
        vc.pause()
        await ctx.response.send_message("Playback paused.")
    else:
        await ctx.response.send_message("Nothing is playing right now.")

@bot.tree.command(name="resume",description='Resume YouTube playback.')
async def resume(ctx: discord.Interaction):
    vc = ctx.guild.voice_client
    if vc.is_paused():
        vc.resume()
        await ctx.response.send_message("Playback resumed.")
    else:
        await ctx.response.send_message("Playback is not paused.")

async def play_next(vc, ctx):
    while queue:
        title, audio_source, length = queue[0]
        vc.play(audio_source, after=lambda e: logging.error(f'Player error: {e}') if e else None)
        await ctx.channel.send(f"Now playing: {title}")
        logging.info(f"Now playing: {title}.")
        while vc.is_playing() or vc.is_paused():
            await asyncio.sleep(1)
        #await ctx.channel.send(f"Finished playing: {title}.")
        logging.info(f"Finished playing: {title}.")
        try:
            queue.pop(0)
        except Exception as e:
            logging.error(f'Error in while loop: {e}')
    await vc.disconnect()
    logging.debug('VC disconnected due to queue being empty.')

@bot.tree.command(name='queue', description='Display the current queue.') # displays links need to change to titles
async def display_queue(ctx: discord.Interaction):
    logging.debug(f'Queue command Author: {ctx.user}')
    if queue:
        upnext = '' if len(queue) <= 1 else 'Up Next: '
        queue_info = '\n'.join([f"__**Currently Playing:**__ **{tuple[0]}**\n{upnext}" if i == 0 else f"{i}. {tuple[0]}" for i, tuple in enumerate(queue)])
        await ctx.response.send_message(f"{queue_info}")
    else:
        await ctx.response.send_message("The queue is empty.") # shouldn't trigger??

@bot.tree.command(name='skip', description='Skips the current audio and plays the next one in the queue.')
async def skip(ctx: discord.Interaction):
    logging.debug(f'Skip command Author: {ctx.user}')
    vc = ctx.guild.voice_client
    if vc and vc.is_playing():
        vc.stop() # stop vc triggers inner while loop of play to break
        await ctx.response.send_message(f"Skipping {queue[0][0]}.")
        logging.info(f"Skipping {queue[0][0]}.")
    else:
        await ctx.response.send_message("Nothing to skip.") 

@bot.tree.command(name='stop', description='Stops playing audio, clears the queue, and disconnects Bot from the voice channel.') # displays error but seems to work regardless
async def stop(ctx: discord.Interaction):
    ### need to find a way to kill the background tasks
    logging.debug(f'Stop command Author: {ctx.user}')
    vc = ctx.guild.voice_client
    if vc:
        vc.stop()
        queue.clear()
        for task in bg_tasks:
            task.cancel()
        await vc.disconnect()
        await ctx.response.send_message("Stopped playing audio, cleared the queue, and disconnected from the voice channel.")
        logging.info("Stopped playing audio, cleared the queue, and disconnected from the voice channel.")
    else:
        await ctx.response.send_message("I'm not connected to a voice channel.")

bot.run(TOKEN)
