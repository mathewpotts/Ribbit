#!/usr/bin/env python3
import sys
import json
from pytube import YouTube, Playlist
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
    if 'playlist' in youtube_url:
        pl = Playlist(youtube_url) # not slow
        logging.debug(pl)
        logging.debug(pl.videos)
        titles = []
        for vid in pl.videos:
            try:
                logging.debug(vid)
                tit = vid.title
                logging.debug(tit)
                titles.append(tit)
            except Exception as e:
                logging.debug(e)
#                retry = True
#                while retry:
#                    try:
#                        wtit = vid.title
#                        #logging.debug(wtit)
#                        title.append(wtit)
#                        retry = False
#                    except Exception as e:
#                        logging.debug(f"WHILE {e}")
                        
        logging.debug(titles)
        #titles = [video.title for video in pl.videos] ## slower 
        #Traceback (most recent call last):
        #  File "/usr/local/lib/python3.11/dist-packages/pytube/__main__.py", line 341, in title
        #self._title = self.vid_info['videoDetails']['title']
        #          ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^
        #KeyError: 'videoDetails'
        video_urls = []
        for i,video in enumerate(pl.videos):
            logging.debug(f"Find URL: {i}. {titles[i]}")
            try: # known problem with unavaiable songs in playlist
                video_urls.append(video.streams.filter(progressive=True, file_extension='mp4').first().url)  # sllllowest
            except: # if problem just skip it...
                continue
        for i, video_url in enumerate(video_urls):
            queue.append([titles[i], video_url])
    else:
        try:
            yt = YouTube(youtube_url, use_oauth=True)
            title = yt.title
            video_url = yt.streams.filter(progressive=True, file_extension='mp4').first().url
            queue.append([title, video_url])
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            raise
    print(json.dumps(queue))

if __name__ == "__main__":
    youtube_url = sys.argv[1]
    preload_songs(youtube_url)
