import os
import random
import asyncio
import discord 
import youtube_dl

from ytdl import YTDLSource, getSimpleMusicPlayer
from dotenv import load_dotenv
from Levenshtein import distance

from discord.ext import commands

testUrl = "https://www.youtube.com/watch?v=jEheNftCtyQ"

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.all()

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
bot.info = None
bot.guessMode = False
bot.currentSong = ""
bot.currentArtist = ""
bot.artistFound = True
bot.songFound = True

queue = []

def checkAnswer(msg, answer, precision=0.25):
    nWordsAnswers = len(answer.split(" "))
    
    splitMsg = msg.split(" ")
    nWordsMsg = len(splitMsg)

    if nWordsAnswers > nWordsMsg:
        return False
    elif nWordsAnswers == nWordsMsg:
        dist = distance(msg, answer) / len(answer)
        return dist <= precision
    else:
        # Test if the answoer is in the few first words or the few last words
        testAnswer = "".join(splitMsg[:nWordsAnswers])
        dist = distance(testAnswer, answer) / len(answer)
        if dist <= precision:
            return True

        testAnswer = "".join(splitMsg[-nWordsAnswers:])
        dist = distance(testAnswer, answer) / len(answer)
        if dist <= precision:
            return True

    return False

def addPoint(user, dic):
    if not user in dic:
        dic[user] = 1
    else:
        dic[user] = dic[user] + 1

class GameInfo:

    def __init__(self, mainChannel, voiceChannel, users, guessChannel=None):
        self.mainChannel = mainChannel
        self.voiceChannel = voiceChannel
        self.users = users
        self.mode = "waiting"
        self.guessChannel = guessChannel
        self.currentPlayer = 0

    def getUserListString(self):
        s = ""
        for user in self.users:
            s += user + ", "
        
        if len(s) > 1:
            s = s[:-2]

        return s
    
    def goNextPlayer(self):
        self.currentPlayer = (self.currentPlayer + 1 ) % len(list(self.users.keys()))

    def getcurrentPlayer(self):
        return list(self.users.keys())[self.currentPlayer]

@bot.command(name='help')
async def help(ctx):
    await ctx.channel.send(">>> Bot commands : \n"
        + " - !init [voice channel] [main text channel] [guess text channel] : initialize blind test \n"
        + " - !start : start the game (This is absolutely not useless, this is pretty and looks professional)\n"
        + " - !play [url] [artist] [song] : play a song for the blind test\n"
        + " - !currentplayer : get the current player\n"
        + " - !skip : skip the current player\n"
        + " - !score : get the scores\n"
        + " - !add [player] : add a player to the game\n"
        + " - !remove [player] : remove a player from the game\n"
        + " - !stop : stop the music\n"
        + " - !yt [url] : play a youtube video in your voice channel\n")


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

@bot.command(name='init')
async def initBot(ctx, channelName, txtChannelName):
    print("Initializing bot bot")
    channel = discord.utils.get(ctx.guild.channels, name=channelName, type=discord.ChannelType.voice)
    
    if channel == None:
        await ctx.channel.send(f"Voice channel \"{channelName}\" not found !")
        return

    txtChannel = discord.utils.get(ctx.guild.channels, name=txtChannelName, type=discord.ChannelType.text)
    if txtChannel == None:
        await ctx.channel.send(f"Text channel \"{txtChannelName}\" not found !")
        return
    elif txtChannel == ctx.channel : 
        await ctx.channel.send(f"Guess channel cannot be the same as the command channel !")
        return
    
    members = channel.members
    users = {}
    for member in members:
        users[member.name] = 0
    

    bot.info = GameInfo(ctx.channel, channel, users, txtChannel)

    await bot.info.mainChannel.send(f"Initialized game with parameters : \n "
        + f" - Voice Channel : {channelName} \n"
        + f" - Song request Channel : {ctx.channel.name} \n"
        + f" - Guess channel : {txtChannel.name if txtChannel != None else None} \n"
        + f" - Players : {bot.info.getUserListString()}")

def wrongArgs(ctx, command):
    if command == "play":
        return "Wrong arguments for the command play. The correct arguments are : {Video Url} {artist name} - {song name}"

@bot.command(name = "play", pass_context=True)
async def play(ctx, url, *argss):

    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return

    voiceChannel = bot.info.voiceChannel
    
    args = " ".join(argss)
    s = args.split("-")
    if len(s) != 2:
        await ctx.channel.send(wrongArgs(ctx, "play"))
        return
    artist = s[0].strip()
    song = s[1].strip()

    # Dowload youtube video
    player = await YTDLSource.from_url(url, loop=bot.loop)

    # Check if we're already connected
    for client in bot.voice_clients:
        if client.channel.id == voiceChannel.id:
            await client.disconnect()

    vc = await voiceChannel.connect()

    bot.info.mode = "playing"

    vc.play(getSimpleMusicPlayer("countdown.mp3"), after=lambda e: print('Player error: %s' % e) if e else None)
    while vc.is_playing():
        await asyncio.sleep(1)

    await ctx.send('Now playing: {}'.format(player.title))
    bot.currentSong = song.lower()
    bot.currentArtist = artist.lower()
    bot.artistFound = False
    bot.songFound = False

    vc.play(player, after=lambda e: print('Player error: %s' % e) if e else None)
    while vc.is_playing():
        await asyncio.sleep(1)

    player.close()
    await vc.disconnect()

@bot.command(name='score')
async def getScore(ctx):
    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return
    
    s = "The current scores are : \n"
    for key, value in bot.info.users.items():
        s += f" - {key} : {value} points \n"

    await ctx.channel.send(s)

@bot.command(name='add')
async def addPlayer(ctx, user):
    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return

    member = None
    for m in ctx.channel.members:
        if m.name.lower() == user.lower() or m.display_name.lower() == user.lower():
            member = m

    if member == None:
        await ctx.channel.send(f"User {user} not found")
        return

    if not member.name in bot.info.users:
        bot.info.users[member.name] = 0
        await ctx.channel.send(f"Player {member.name} added")
    else:
        await ctx.channel.send(f"Player {member.name} is already in the list of players")

    # if not user in bot.info.users:
    #     bot.info.users[user] = 0
    #     await ctx.channel.send(f"Player {user} added")
    # else:
    #     await ctx.channel.send(f"Player {user} is already in the list of players")

@bot.command(name='remove')
async def removePlayer(ctx, user):
    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return
        
    if user not in bot.info.users:
        await ctx.channel.send(f"User {user} not found !")
        return

    currentP = bot.info.getcurrentPlayer()
    bot.info.users.pop(user, None)
    if currentP == user:
        if bot.info.currentPlayer >= len(list(bot.info.users.keys())):
            bot.info.currentPlayer = 0
    else:
        bot.info.currentPlayer = list(bot.info.users.keys()).index(currentP)

    await ctx.channel.send(f"It's {bot.info.getcurrentPlayer()} turn !")

@bot.command(name='start')
async def startGame(ctx):
    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return
    
    await ctx.channel.send(f"Game started with players {bot.info.getUserListString()}")
    await ctx.channel.send(f"It's {bot.info.getcurrentPlayer()} turn !")


@bot.command(name='currentplayer')
async def currentPlayer(ctx):
    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return
        
    await ctx.channel.send(f"It's {bot.info.getcurrentPlayer()} turn !")

@bot.command(name='skip')
async def skipPlayer(ctx):
    if bot.info == None:
        await ctx.channel.send(f"The bot needs to be initialized !")
        return
    
    bot.info.goNextPlayer()
    await ctx.channel.send(f"It's {bot.info.getcurrentPlayer()} turn !")



@bot.command(name='stop')
async def stopBot(ctx):
    for client in bot.voice_clients:
        await client.disconnect()


@bot.command(name='exit')
async def exitBot(ctx):
    print("Shuting down bot")
    for vc in bot.voice_clients:
        await vc.disconnect()
    await bot.close()

@bot.event
async def on_message(message):
    if message.author.bot == True:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    if bot.info != None and bot.info.guessChannel != None and bot.info.guessChannel.id == message.channel.id:
        
        if bot.artistFound == False:
            artistFound = checkAnswer(message.content.lower(), bot.currentArtist)
            # Re-adding bot.artistFound == False for a bit of lazy thread safety
            if artistFound and bot.artistFound == False: 
                bot.artistFound = True
                await message.channel.send(f"{message.author.name} found the artist ! The artist was : {bot.currentArtist}")
                addPoint(message.author.name, bot.info.users)
        
        if bot.songFound == False:
            songFound = checkAnswer(message.content.lower(), bot.currentSong)
            if songFound and bot.songFound == False: 
                bot.songFound = True
                await message.channel.send(f"{message.author.name} found the song name ! The song was : {bot.currentSong}")
                addPoint(message.author.name, bot.info.users)

        if bot.artistFound and bot.songFound and bot.info.mode == "playing":
            bot.info.mode = "waiting"
            bot.info.goNextPlayer()
            await message.channel.send(f"It's {bot.info.getcurrentPlayer()} turn !")


@bot.command(name = "addToQueue", pass_context=True)
async def queueSong(context, url):
    print("addToQueue")
    queue.append(url)


@bot.command(name = "yt", pass_context=True)
async def testYt(context, url):
    user = context.message.author
    voiceChannel = user.voice.channel
    
    ytplayer = await YTDLSource.from_url(url, loop=bot.loop)

    ## Check if we're already connected
    for client in bot.voice_clients:
        if client.channel.id == voiceChannel.id:
            await client.disconnect()

    vc = await voiceChannel.connect()

    await context.send('Now playing: {}'.format(ytplayer.title))    
    vc.play(ytplayer, after=lambda e: print('Player error: %s' % e) if e else None)
    while vc.is_playing():
        await asyncio.sleep(1)

    ytplayer.close()
    await vc.disconnect()

@bot.command(name = "playQueue", pass_context=True)
async def playQueue(context):
    print("playQueue")

    user = context.message.author
    voiceChannel = user.voice.channel


    while(len(queue) != 0):

        url = queue.pop()
        ytplayer = await YTDLSource.from_url(url, loop=bot.loop)

        ## Check if we're already connected
        for client in bot.voice_clients:
            if client.channel.id == voiceChannel.id:
                await client.disconnect()

        vc = await voiceChannel.connect()

        await context.send('Now playing: {}'.format(ytplayer.title))    
        vc.play(ytplayer, after=lambda e: print('Player error: %s' % e) if e else None)
        while vc.is_playing():
            await asyncio.sleep(1)

        ytplayer.close()
        await vc.disconnect()


@bot.event
async def on_error(event, *args, **kwargs):
    # TODO
    return


bot.run(TOKEN)