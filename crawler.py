#!/usr/bin/env python
# -*- coding:utf-8 -*-

'''

GuitarChina BBS Crawler 

Author: Zakk Zhu
Repository: github/zhujiaqi/GC_Crawler

Requirements:
1. Python 2.7
2. sqlite3

Installation:
1. initialize gc.db
2. run python crawler.py

Features:
1. Craw the pages and save them locally.
2. Stripe the styles so you got what you need...in a organized way.

You are free to use this code snipplet as long as its not for commercial proposes and within the restrictions of the laws.

It comes with absolutely no guarantee so if anything didn't work as expected, bail out. (or fix it)
However, you are welcome to make it better, some nice to have improvements:
1. Kill the captcha and make the login part working. (So you can see & save images)
2. Option to dump the DB.
3. Daemon process to run this remotely and by demands. 
4. Email the results to designated addresses.
...

'''

'''start: configurations'''

username = 'your gc username' #login username
password = 'your gc password' #login password
PAGE_TOTAL = 5 #number of pages you'd like to craw for each forums
FORUM_IDS = [102, 105] #id for which forums you'd like to craw
DEBUG = True

'''end: configurations'''

import urllib
import urllib2
import os
import re
import time
import cookielib  
import datetime
import sys
import sqlite3
import hashlib
import httplib

def md5sum(t):
    return hashlib.md5(t).hexdigest()

conn = sqlite3.connect("gc.db")
conn.isolation_level = None
conn.text_factory = str
cur = conn.cursor()

cur.execute("create table if not exists items(id integer primary key autoincrement, url varchar(128), content_md5 varchar(128))")
cur.execute("create unique index if not exists url_index on items(url)")

if not os.path.isdir('contents'):
    os.mkdir('contents')
    
if not os.path.isdir('raw'):
    os.mkdir('raw')

forum = 'http://bbs.guitarchina.com/forum-%s-%s.html'
cut_token = 'separation'
token = r'<span id="thread_\d+"><a href="(.+)">(.+)</a></span>'
post = 'http://bbs.guitarchina.com/%s'
post_token = r'<div class="postmessage defaultpost">(.+)</div>'

login_page = "http://bbs.guitarchina.com/logging.php?action=login"  
lpc = urllib.urlopen(login_page).read()

if DEBUG:
    with open('temp1.html','w') as f:
        f.write(lpc)
    
login_page += '&loginsubmit=true'
t = '<input type="hidden" name="formhash" value="(.+)" />'
formhash = re.search(t, lpc).groups()[0]

if DEBUG:
    print formhash
    
cj = cookielib.LWPCookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))  
opener.addheaders = [('User-agent','Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)')]  

data = urllib.urlencode(
    {
        "loginfield": 'username',
        "username": username,
        "password": password,
        "cookietime": "2592000",
        "formhash": formhash,
        "userlogin": 'true',
        "questionid": '0',
        "answer": '',
        "loginmode": '',
        "styleid": '',
    }
)  

# ==========
# simulate login. (NOT WORKING)

# print data
# r = opener.open(login_page, data).read()
# with open('temp2.html','w') as f:
    # f.write(r)
    
# ==========

items = []
for i in FORUM_IDS:
    for j in range(1, PAGE_TOTAL+1):
        link = forum % (str(i), j)
        u = opener.open(link)
        content = u.read()
        if DEBUG:
            print link, 'get list'
        with open('raw/forum-%s-%s.html' % (str(i), j), 'w') as f:
            f.write(content)
        if j == 1:
            cut = content.find(cut_token)
            content = content[cut:]
        matches = re.findall(token, content)
        for match in matches:
            link = post % match[0]
            tries = 3
            while 1:
                if tries < 0:
                    if DEBUG:
                        print match[0], 'skipped!'
                    break
                try:
                    u = opener.open(link)
                    inner_page_content = u.read()
                    break
                except httplib.IncompleteRead:
                    tries -= 1
                    continue
            if DEBUG:
                print link, 'get item'
            time.sleep(0.1)
            with open('raw/' + match[0], 'w') as f:
                f.write(inner_page_content)
            left = inner_page_content.find('<h1>')
            right = inner_page_content.find('<div id="post_rate_div_')
            inner_page_content = inner_page_content[left:right]
            inner_page_content = re.search(post_token, inner_page_content, re.DOTALL).groups()[0] + '</div>'
            items.append(match)
            with open('contents/' + match[0], 'w') as inner_f:
                inner_f.write(inner_page_content)
                
            newtext = md5sum(inner_page_content)
            item_in_db = cur.execute("select * from items where url == ?", (match[0],)).fetchone()
            if item_in_db:
                oldtext = item_in_db[1]
                if oldtext != newtext:
                    if DEBUG:
                        print match[0], 'has changed'
                    cur.execute("update items set content_md5 = ? where url = ?", (newtext, match[0]))
            else:   
                cur.execute("insert into items values(null,?,?)", (match[0], newtext))
                
with open('test_result_%s_%d.html' % (str(datetime.date.today()), int(time.time())), 'w') as tf:
    tf.write('<html>')
    for item in items:
        tf.write('<div style="margin-top:10px;"><a href="contents/%s">%s</a>&nbsp;&nbsp;<a target="_blank" href="http://bbs.guitarchina.com/%s">[Original]</a></div>' % (item[0], item[1], item[0]))
        
    tf.write('</html>')
    