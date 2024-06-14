#!/usr/bin/env python3
import discord
import asyncio
from discord.ext import commands
from pytube import YouTube, Playlist

TOKEN = "TOKEN ;-)"

# Setting command prefix
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# Define a list for queueing videos
queue = []

# Make bot leave after songs in queue are exhausted
def on_song_end(ctx, error):
    if not queue:
        asyncio.run_coroutine_threadsafe(ctx.voice_client.disconnect(), bot.loop)

async def preload_songs(ctx, youtube_url):
    print("Im preloading songs...")
    if 'playlist' in youtube_url:
        pl = Playlist(youtube_url)
        titles = [video.title for video in pl.videos]
        video_urls = [video.streams.filter(progressive=True, file_extension='mp4').first().url for video in pl.videos] # source urls
        for i, video_url in enumerate(video_urls):
            audio_source = discord.FFmpegPCMAudio(video_url)
            queue.append([titles[i], video_url, audio_source])
        await ctx.send(f'Adding {len(video_urls)} to queue.')
    else:
        yt = YouTube(youtube_url)
        title = yt.title
        video_url = yt.streams.filter(progressive=True, file_extension='mp4').first().url # source url
        audio_source = discord.FFmpegPCMAudio(video_url)
        queue.append([title, video_url, audio_source])
        if len(queue) > 1: # if there is stuff in the queue then report to user that it is being added
            await ctx.send(f'Adding {title} to queue.')

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel is not None and after.channel is None and member == bot.user:
        await member.guild.voice_client.disconnect()

@bot.command(name='play', help='post youtube link') # pauses playing audio when adding things to queue
async def play(ctx, youtube_url):
    # Grab author voice channel and print it to log
    voice_channel = ctx.author.voice.channel
    print('Author:',ctx.author,', Channel:', voice_channel,'URL:', youtube_url)

    #### CHECKS ####
    # Check if Author is in  channel
    if not voice_channel:
        await ctx.send(f'{ctx.author} you need to be in a voice channel before using me to play audio.')
        return 1
    # Check if YouTube link
    if 'youtube' not in youtube_url:
        await ctx.send(f'{youtube_url} is not from YouTube. I can only play YouTube videos.')
        return 1
    #### Preload songs to queue ####
    #await preload_songs(ctx, youtube_url)
    ###############################
    # Check if Bot is already in voice channel
    vc = ctx.voice_client
    if not vc:
    	await preload_songs(ctx, youtube_url)
    	vc = await voice_channel.connect()
    else:
        print("I'm already in voice channel")
        await preload_songs(ctx, youtube_url)
        return 0
    #### END CHECKS ####

    # Loop over songs from queue
    while queue:
        audio = queue[0][2]
        title = queue[0][0]
        vc.play(audio)
        await ctx.send(f"Now playing: {title}.")
        while vc.is_playing():
            await asyncio.sleep(1)
        await ctx.send(f"Now finished playing: {title}.")
        queue.pop(0)
    vc.stop()
    await vc.disconnect()

@bot.command(name='queue', help='Display the current queue') # displays links need to change to titles
async def display_queue(ctx):
    if queue:
        queue_info = '\n'.join([f"{i + 1}. {tuple[0]}" for i, tuple in enumerate(queue)])
        await ctx.send(f"Current Queue:\n{queue_info}")
    else:
        await ctx.send("The queue is empty.")

@bot.command(name='skip', help='skips the current audio and plays the next one in the queue')
async def skip(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
        queue.pop(0)
        await ctx.send("Skipping current audio.")

@bot.command(name='stop', help='stops playing audio, clears the queue, and disconnects from the voice channel') # displays error but seems to work regardless
async def stop(ctx):
    vc = ctx.voice_client
    if vc:
        vc.stop()
        queue.clear()
        await vc.disconnect()
        await ctx.send("Stopped playing audio, cleared the queue, and disconnected from the voice channel.")
    else:
        await ctx.send("I'm not connected to a voice channel.")

bot.run(TOKEN)
