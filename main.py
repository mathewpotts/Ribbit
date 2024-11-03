#!/usr/bin/env python3
import discord
import asyncio
import subprocess
import json
import logging
from time import sleep
from discord.ext import commands
from pytube import YouTube, Playlist

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

# Define a list of background tasks
bg_tasks = []

# Define Batch Size for Playlist loading
BATCH = 1
BATCH_WAIT = 5

async def preload_songs(ctx, youtube_url):
    logging.info(f'Preloading {youtube_url}.')
    processes = {}
    stdout = {}
    stderr = {}
    if 'playlist' in youtube_url:
        await ctx.send(f'Preloading Playlist. I will add these songs to the queue {BATCH} song at a time to a total queue size of {BATCH_WAIT}. Then I will wait for more queue space to add more songs.')
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
        await ctx.send(f'Preloading song. Please wait for me to connect to VC.')
        logging.info(f'Preloading song. Please wait for me to connect to VC.')
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
    await ctx.send(f'Adding {len(songs)} songs to the queue.')

@bot.event
async def on_ready():
    logging.info(f'We have logged in as {bot.user}')

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

@bot.command(name='play', help='Play and queue YouTube links. Example: $play <YouTube URL>')
async def play(ctx, youtube_url):
    # Check if Author is in  channel
    try:
        voice_channel = ctx.author.voice.channel
    except AttributeError:
        logging.info(f'{ctx.author} you need to be in a voice channel before using me to play audio.')
        await ctx.send(f'{ctx.author} you need to be in a voice channel before using me to play audio.')
        return

    # Check if YouTube link
    if 'youtube' not in youtube_url:
        await ctx.send(f'{youtube_url} is not from YouTube. I can only play YouTube videos.')
        logging.info(f'{youtube_url} is not from YouTube. I can only play YouTube videos.')
        return

    # Grab author voice channel and print it to log
    logging.debug(f'Play command Author: {ctx.author}, Channel: {voice_channel}, URL: {youtube_url}')

    #### Preload songs to queue ####
    proc = bot.loop.create_task(preload_songs(ctx, youtube_url))
    bg_tasks.append(proc)

    # Check if Bot is already in voice channel
    vc = ctx.voice_client
    if not vc:
        while len(queue) == 0:
            await asyncio.sleep(1)
        vc = await voice_channel.connect()
        logging.info('Entering VC.')
    else:
        return

    await play_next(vc, ctx)

@bot.command(name='pause', help='Pause YouTube playback.')
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Playback paused.")
    else:
        await ctx.send("Nothing is playing right now.")

@bot.command(name='resume', help='Resume YouTube playback.')
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("Playback is not paused.")

async def play_next(vc, ctx):
    while queue:
        title, audio_source, length = queue[0]
        vc.play(audio_source, after=lambda e: logging.error(f'Player error: {e}') if e else None)
        await ctx.send(f"Now playing: {title}.")
        logging.info(f"Now playing: {title}.")
        while vc.is_playing() or vc.is_paused():
            await asyncio.sleep(1)
        await ctx.send(f"Finished playing: {title}.")
        logging.info(f"Finished playing: {title}.")
        try:
            queue.pop(0)
        except Exception as e:
            logging.error(f'Error in while loop: {e}')
    await vc.disconnect()
    logging.debug('VC disconnected due to queue being empty.')

@bot.command(name='queue', help='Display the current queue.') # displays links need to change to titles
async def display_queue(ctx):
    logging.debug(f'Queue command Author: {ctx.author}')
    if queue:
        queue_info = '\n'.join([f"Currently Playing: {tuple[0]}" if i == 0 else f"{i}. {tuple[0]}" for i, tuple in enumerate(queue)])
        await ctx.send(f"Current Queue:\n{queue_info}")
    else:
        await ctx.send("The queue is empty.") # shouldn't trigger??

@bot.command(name='skip', help='Skips the current audio and plays the next one in the queue.')
async def skip(ctx):
    logging.debug(f'Skip command Author: {ctx.author}')
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop() # stop vc triggers inner while loop of play to break
        await ctx.send(f"Skipping {queue[0][0]}.")
        logging.info(f"Skipping {queue[0][0]}.")
    else:
        await ctx.send("Nothing to skip.") # does this ever trigger??

@bot.command(name='stop', help='Stops playing audio, clears the queue, and disconnects Bot from the voice channel.') # displays error but seems to work regardless
async def stop(ctx):
    ### need to find a way to kill the background tasks
    logging.debug(f'Stop command Author: {ctx.author}')
    vc = ctx.voice_client
    if vc:
        vc.stop()
        queue.clear()
        for task in bg_tasks:
            task.cancel()
        await vc.disconnect()
        await ctx.send("Stopped playing audio, cleared the queue, and disconnected from the voice channel.")
        logging.info("Stopped playing audio, cleared the queue, and disconnected from the voice channel.")
    else:
        await ctx.send("I'm not connected to a voice channel.")

bot.run(TOKEN)
