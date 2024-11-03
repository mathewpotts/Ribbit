#!/usr/bin/env python3
import sys
import json
from pytube import YouTube
import logging

logging.basicConfig(filename='/home/potts/ribbit.log',
                    filemode='a',
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)

# Fixes age restricted errors. Actually age restricted videos will still not work.
from pytube.innertube import _default_clients
_default_clients["ANDROID"]["context"]["client"]["clientVersion"] = "19.08.35"
_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID"]


def preload_songs(youtube_url):
    queue = []
    logging.info(f"In preload {youtube_url}")    
    
    try:
        yt = YouTube(youtube_url, use_oauth=True)
        title = yt.title
        length = yt.length # in seconds
        logging.debug(title)
        video_url = yt.streams.filter(progressive=True, file_extension='mp4').first().url
        queue.append([title, video_url, length])
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        raise
    print(json.dumps(queue))

if __name__ == "__main__":
    youtube_url = sys.argv[1]
    preload_songs(youtube_url)
