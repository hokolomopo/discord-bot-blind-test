# Thanks https://stackoverflow.com/questions/56060614/how-to-make-a-discord-bot-play-youtube-audio


import discord
import youtube_dl
import os
import asyncio
import yt_dlp

yt_dlp.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': {'default': '%(extractor)s-%(id)s-%(title)s.%(ext)s' },
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, filename, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')
        self.filename = filename

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        # Process URL to delete timestamp and playlist
        url = url.split("&")[0]

        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), filename,  data=data)

    def close(self):
        try:
            if self.filename != None :
                os.remove(self.filename)
        except :
            print("Could not delete file " + self.filename)


def getSimpleMusicPlayer(filename):
    return discord.FFmpegPCMAudio(filename, **ffmpeg_options)