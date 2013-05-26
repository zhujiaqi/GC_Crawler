#!/usr/bin/env python
# -*- coding:utf-8 -*-

'''

GuitarChina BBS Crawler 

Author: Zakk Zhu
Repository: github/zhujiaqi/GC_Crawler

Requirements:
1. Python 2.7
2. Sqlite3
3. Gmail account (optional)

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
2. Options for dumping the DB.
3. Daemon process to run this remotely and by demands. 
4. ...

'''

'''start: configurations'''

DEBUG = False
USERNAME = 'your gc username' #login username
PASSWORD = 'your gc password' #login password
PAGE_TOTAL = 10 #number of pages you'd like to craw for each forums
FORUM_IDS = [102, 105] #id for which forums you'd like to craw
MAIL_CONFIG = {
    'enabled': True,
    'sender': 'you@gmail.com',
    'password': 'password',
    'recipients': ['me@gmail.com'],
}

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
import zipfile
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.mime.base import MIMEBase
from email import encoders

def send_gmail(email_config, filename, subject='GC Crawler Test Email', text=u'Attachment'):
    msg = MIMEMultipart()
    part1 = MIMEText(text.encode('utf-8'), 'plain', _charset='utf-8')
    msg.attach(part1)
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = str(Header('GC Crawler', 'utf-8')) + ' <%s>' % email_config['sender']
    for email in email_config['recipients']:
        msg.add_header('To', email)

    attachment = MIMEBase('application', 'zip')
    zf = open(filename, 'rb')
    attachment.set_payload(zf.read())
    zf.close()
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition','attachment;filename="%s"' % filename)
    msg.attach(attachment)
    session = smtplib.SMTP('smtp.gmail.com', 587)
    session.starttls()
    session.login(email_config['sender'], email_config['password'])
    session.sendmail(email_config['sender'], email_config['recipients'], msg.as_string())
    session.quit()

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
    with open('login_page.html','w') as f:
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
        "username": USERNAME,
        "password": PASSWORD,
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
filenames = []
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
            filenames.append('contents/' + match[0])
                
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
                
stamp = '%s_%d' % (str(datetime.date.today()), int(time.time()))
with open('test_result_%s.html' % stamp, 'w') as tf:
    tf.write('<html>')
    for item in items:
        tf.write('<div style="margin-top:10px;"><a href="contents/%s">%s</a>&nbsp;&nbsp;<a target="_blank" href="http://bbs.guitarchina.com/%s">[Original]</a></div>' % (item[0], item[1], item[0]))
        
    tf.write('</html>')
filenames.append('test_result_%s.html' % stamp)
    
with zipfile.ZipFile('%s.zip' % stamp, 'w') as myzip:
    for fn in filenames:
        myzip.write(fn)
        if DEBUG:
            print fn, 'added to zip'

if MAIL_CONFIG['enabled']:
    send_gmail(MAIL_CONFIG, '%s.zip' % stamp, 'GC Crawler %s' % stamp)