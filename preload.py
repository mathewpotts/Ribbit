#!/usr/bin/env python3
import sys
import json
from pytube import YouTube, Playlist

def preload_songs(youtube_url):
    queue = []
    try:
        if 'playlist' in youtube_url:
            pl = Playlist(youtube_url)
            titles = [video.title for video in pl.videos]
            video_urls = [video.streams.filter(progressive=True, file_extension='mp4').first().url for video in pl.videos]
            for i, video_url in enumerate(video_urls):
                queue.append([titles[i], video_url])
        else:
            yt = YouTube(youtube_url)
            title = yt.title
            video_url = yt.streams.filter(progressive=True, file_extension='mp4').first().url
            queue.append([title, video_url])
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
    print(json.dumps(queue))

if __name__ == "__main__":
    youtube_url = sys.argv[1]
    preload_songs(youtube_url)
