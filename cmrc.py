#!/usr/bin/python
import praw
import requests
import re
import sys
import time
import os
import datetime

logBuf = ""
logTimeStamp = ""
searchResult = ""

USERNAME            = ""
PASSWORD            = ""
SUBREDDIT           = ""


def readConfig ():
    f = open('cmrc.conf', 'r')
    buf = f.readlines()
    f.close()

    for b in buf:
        if b[0] == '#' or len(b) < 5:
            continue

        if b.startswith('username:'):
            USERNAME = b[len('username:'):].strip()

        if b.startswith('password:'):
            PASSWORD = b[len('password:'):].strip()

    if not USERNAME or not PASSWORD:
        print ("Missing param from conf file")
        quit()

    return USERNAME, PASSWORD




def init (useragent):
    r = praw.Reddit(user_agent=useragent)
    # so that reddit wont translate '>' into '&gt;'
    r.config.decode_html_entities = True
    return r


def login (r, username, password):
    Trying = True
    while Trying:
        try:
            r.login(username, password)
            print('Successfully logged in')
            Trying = False
        except praw.errors.InvalidUserPass:
            print('Wrong Username or Password')
            quit()
        except Exception as e:
            print("%s" % e)
            time.sleep(5)




#####################################################################
def DEBUG(s, start=False, stop=False):

    global logBuf
    global logTimeStamp

    print (s)

    logBuf = logBuf + s + "\n\n"
    if stop:
        r.submit("bookbotlog", logTimeStamp, text=logBuf)
        logBuf = ""


#####################################################################

def getStickyLoc (s):

    count = 0
    index = -1
    useComma = ''

    for x in s:
        if "BOIB STICKY" in x:
            index = count
            break
        count += 1


    if index < 0:
        return index, useComma

    for i in range(index, -1, -1):
        if s[i].startswith(".comments-page"):
            useComma = ','
        if s[i].startswith('}'):
            return i+1, useComma

    return -1, False


def doStickyComment (r,s,m):
    #
    # r=reddit, s=msgbody, m=msgauthor
    #

    #.comments-page .sitetable.nestedlisting>.thing.id-t1_cmdajj7
    #/* dont delete this line BOIB STICKY COMMENTS */

    stickyLine = ".comments-page .sitetable.nestedlisting>.thing.id-t1_"

    url = s.strip()
    if url[-1] == "/":
        url = url[:-1]

    index = url.rfind("/")
    if index < 0:
        returnBuf += "**Error**: Can't find comment id in url: %s\n\n" % url

    else:
        id = url[index+1:]
        returnBuf = "Adding Sticky Comment for **%s** (%s)\n\n" % (id, url)

        sr = r.get_subreddit("books")
        sheet = sr.get_stylesheet()['stylesheet']
        sheets = sheet.split("\n")

        if id in sheet:
            thisThing = "http://www.reddit.com/message/compose/?to=boib&subject=WTF?&message=This%20already%20sticky:%0a%0a" + s
            returnBuf += "**Error**: Comment already sticky.  Don't agree?  Send a [WTF](%s) message to /u/boib\n\n" % thisThing

        else:
            index, useComma = getStickyLoc(sheets)
            if index <= 0:
                returnBuf += "**Error**: can't find sticky location in CSS code\n\nBetter call /u/boib\n\n"
            else:
                print (str(index-1) + sheets[index-1])
                print (str(index) + sheets[index])
                print (str(index+1) + sheets[index+1])
                sheets.insert(index, stickyLine + id + useComma)
                print (stickyLine + id + useComma + "   " + str(index))
                sheet = "\n".join(sheets)
                e = sr.set_stylesheet(sheet)

                returnBuf += "Sticky success!\n\n"

    return returnBuf


def doReplies (replies, searchStr, authorSearch):
    global searchResult

    for reply in replies:
        for reply in replies:
#            if authorSearch:
#                if not reply.author:
#                    continue
#                text = reply.author.name
#            else:
#                text = reply.body

            #if re.search(searchStr, text, re.I):
            if re.search(searchStr, reply.body, re.I):
                #print ("https://www.reddit.com/message/messages/" + reply.parent_id[3:])
                searchResult += "https://www.reddit.com/message/messages/" + reply.parent_id[3:] + "\n\n"
                return True

            if reply.replies:
                if doReplies(reply.replies, searchStr, authorSearch):
                    return True

    return False


def searchModMail (r,s,m):
    #
    # r=reddit, s=msgbody, m=msgauthor
    #
    global searchResult
    authorSearch = False


    searchStr = s.strip()
    returnBuf = "Searching for **%s**\n\n" % searchStr
    searchResult = ""

#    if searchStr.startswith('author:'):
#        searchStr = searchStr[len('author:'):].strip()
#        authorSearch = True

    try:
        inbox = r.get_mod_mail(subreddit='books', limit=1000)

        if not inbox:
            returnBuf += "aint got no messages\n\n"
        else:
            for inboxMsg in inbox:
                if re.search(searchStr, inboxMsg.body, re.I):
                    searchResult += "https://www.reddit.com/message/messages/" + inboxMsg.fullname[3:] + "\n\n"
                    continue

                if inboxMsg.replies:
                    doReplies(inboxMsg.replies, searchStr, authorSearch)


    except Exception as e:
        returnBuf += 'An error has occured: %s ' % (e)

    if not searchResult:
        returnBuf += "Did not find **%s**" % searchStr
    else:
        returnBuf += searchResult

    return returnBuf



##############################################################################



if __name__=='__main__':
    #
    # init and log into reddit
    #

    SUBREDDIT = "books"
    USERNAME,PASSWORD = readConfig()

    print("==============================")
    r = init("cmrc - /u/"+USERNAME)
    login(r, USERNAME, PASSWORD)
    print("==============================")


    commands = {
        "searchModMail":    searchModMail,
        "stickyComment":    doStickyComment,
    }



    sr = r.get_subreddit(SUBREDDIT)
    mods = sr.get_moderators()

    while True:
        time.sleep(10)
        try:
            inboxMsg = None
            inbox = r.get_unread(limit=300)
            print ("after get_unread")

            if not inbox:
                print ("aint got no messages")

            for inboxMsg in inbox:
                print ("after for inboxMsg")
                isMod = False
                error = False
                cmd = ""
                subred = ""
                logTimeStamp = "cmrc - /r/" + SUBREDDIT + " - " + time.strftime("%d%b%Y-%H:%M:%S")

                print ("msg from " + inboxMsg.author.name)
                if inboxMsg.author.name == "mod_mailer":
                    inboxMsg.mark_as_read()
                    inboxMsg = None
                    continue

                if inboxMsg.subject == "comment reply":
                    inboxMsg.mark_as_read()
                    inboxMsg = None
                    continue

                DEBUG("Msg **%s** from **%s**" % (inboxMsg.subject, inboxMsg.author.name))

                #
                # did the msg come from a moderator?
                #
                for mod in mods:
                    if mod.name == inboxMsg.author.name:
                        isMod = True
                        break

                if not isMod:
                    msg = "*I am a bot* and I only talk to /r/books moderators."
                    print(msg)
                    error = True

                #
                # did they send the cmd and subreddit in the subject field?
                #
                if not error:
                    try:
                        cmd, subred = inboxMsg.subject.split()
                    except:
                        pass

                    if not cmd or not subred:
                        msg = "unknown cmd: (%s) " % inboxMsg.subject.strip()
                        print(msg)
                        error = True

                #
                # is the subreddit valid?
                #
                if not error:
                    if subred != 'books' and subred != "boibtest":
                        msg = "invalid subreddit: " + subred
                        print(msg)
                        error = True

                #
                # if the cmd is valid, execute!
                #
                if not error:
                    if cmd in commands:
                        msg = commands[cmd](r, inboxMsg.body, inboxMsg.author.name)
                        #DEBUG("Reply to (%s):\n\n%s" % (inboxMsg.author.name, msg), stop=True)
                    else:
                        msg = "unknown cmd: (%s) (%s) " % (cmd, subred)

                #
                # log it, reply to sender, mark it read
                #
                DEBUG(msg, stop=True)
                inboxMsg.reply(msg)
                inboxMsg.mark_as_read()
                inboxMsg = None


        except Exception as e:
            DEBUG('An error has occured: %s ' % (e))
            if inboxMsg:
                try:
                    inboxMsg.reply("**Error:** " + e)
                    inboxMsg.mark_as_read()
                    inboxMsg = None
                except:
                    pass
                DEBUG('An error has occured: %s ' % (e))
            continue




