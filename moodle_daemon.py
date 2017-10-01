#!/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import copy
import logging
from datetime import datetime
from moodle_db_create import Base
from moodle_db_create import CCourse
from moodle_db_create import FFile
from moodle_db_create import MMedia
from moodle_db_create import UUser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

engine = create_engine('sqlite:///config/moodleusers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

config = configparser.ConfigParser()
config.read('config/config.ini')
updater = Updater(token=config['DEFAULT']['BotToken'])
dispatcher = updater.dispatcher

default_semester = "WiSe 2016-17"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def send_or_edit(bot, update, text, reply_markup):
    try:
        message_id = update.callback_query.message.message_id
        chat_id = update.callback_query.message.chat.id
        bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
    except AttributeError:
        bot.sendMessage(text=text, chat_id=update.message.chat.id, reply_markup=reply_markup,
                        parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)


def CheckUser(bot, update, arg=None):
    session = DBSession()
    try:
        chat = update.message.chat
    except AttributeError:
        chat = update.callback_query.message.chat
    entry = session.query(UUser).filter(UUser.id == chat.id).first()
    if not entry:
        # Nutzer ist neu
        new_user = UUser(id=chat.id, first_name=chat.first_name, last_name=chat.last_name, username=chat.username,
                         title=chat.title, notifications=True, semester=default_semester, counter=0)
        session.add(new_user)
        session.commit()
        new_usr = copy.deepcopy(new_user)
        message = "Dieser Bot bietet Zugriff auf alle Moodle-Dateien zum Bachelor Elektro- und Informationstechnik ab " \
                  "WS16/17. "
        bot.sendMessage(chat_id=chat.id, text=message, reply_markup=telegram.ReplyKeyboardHide())
        session.close()
        return new_usr
    else:
        entry.counter += 1
        if arg is not None:
            entry.current_selection = arg
        ent = copy.deepcopy(entry)
        session.commit()
        session.close()
        return ent


def Semester(bot, update):  # Semesterauswahl anzeigen
    CheckUser(bot, update)
    session = DBSession()
    semesters = list()
    entries = session.query(CCourse).distinct(CCourse.semester).group_by(CCourse.semester).all()
    for entry in entries:
        semesters.append(entry.semester)
    button_list = []
    for entry in sorted(semesters):
        button_list.append([InlineKeyboardButton(entry, callback_data="4$" + entry)])
    reply_markup = InlineKeyboardMarkup(button_list)
    send_or_edit(bot, update, "Bitte wähle ein Semester aus.", reply_markup)
    session.close()


def SetSemester(bot, update):
    usr = CheckUser(bot, update)
    # Save the new semester
    dat = update.callback_query.data.split("$")
    newsemester = dat[1]
    if newsemester == usr.semester:
        # no change
        ShowHome(bot, update, usr, "Semester nicht geändert.")
    else:
        session = DBSession()
        user = session.query(UUser).filter(UUser.id == usr.id).first()
        user.semester = newsemester
        session.commit()
        session.close()
        ShowHome(bot, update, usr, "Semester geändert auf " + newsemester)


def SetNotifications(bot, update, arg):
    usr = CheckUser(bot, update)
    session = DBSession()
    user = session.query(UUser).filter(UUser.id == usr.id).first()
    if int(arg) == int(user.notifications):
        ShowHome(bot, update, usr, "Benachrichtigungen nicht geändert.")
    else:
        user.notifications = bool(int(arg))
        session.commit()
        usr.notifications = bool(int(arg))
        options = ["deaktiviert.", "aktiviert."]
        ShowHome(bot, update, usr, "Benachrichtigungen wurden " + options[int(arg)])
        session.rollback()
    session.close()


def ShowCourses(bot, update):
    usr = CheckUser(bot, update)
    session = DBSession()
    entries = session.query(CCourse).filter(CCourse.semester == usr.semester).all()
    button_list = []
    for entry in entries:
        button_list.append([InlineKeyboardButton(entry.name, callback_data="1$" + str(entry.id))])
    button_list.append([InlineKeyboardButton("🏠 Home", callback_data="0")])
    reply_markup = InlineKeyboardMarkup(button_list)
    send_or_edit(bot, update, "Bitte wähle einen Kurs aus.", reply_markup)
    session.close()


def ShowCourseContent(bot, update, arg):
    CheckUser(bot, update, arg)
    session = DBSession()
    # erstmal schauen ob Videos exisistieren
    entry = session.query(MMedia).filter(MMedia.course == arg).first()
    if not not entry:
        button_list = [
            [InlineKeyboardButton("🏠 Home", callback_data="0"), InlineKeyboardButton("🔍 Kurse", callback_data="1"),
             InlineKeyboardButton("🎞️ Videos", callback_data="6$" + arg)]]
    else:
        button_list = [
            [InlineKeyboardButton("🏠 Home", callback_data="0"), InlineKeyboardButton("🔍 Kurse", callback_data="1")]]
    reply_markup = InlineKeyboardMarkup(button_list)
    # nun die Elemente in Form bringen
    entries = session.query(FFile).filter(FFile.course == arg).all()
    if len(entries) > 0:
        message = {0: "Dateien zu [" + entries[0].coursedata.name.replace("[", "(").replace("]",
                   ")") + "](https://www.moodle.tum.de/course/view.php?id=" + str(entries[0].course) + "): \n"}
    else:
        message = {0: "Noch keine Dateien vorhanden."}
    counter = 0
    for ent in entries:
        toadd = "[" + ent.title + "](https://t.me/tummoodle/" + ent.message_id + ")\n" if ent.message_id != "0" else "[" + ent.title + " (extern)](" + ent.url + ")\n"
        if len(message[counter] + toadd) > 4096:
            counter += 1
            message[counter] = toadd
        else:
            message[counter] += toadd

    if len(message) > 1:
        send_or_edit(bot, update, message[0], None)
        count = 1
        while count + 2 <= len(message):
            bot.sendMessage(text=message[count], chat_id=update.callback_query.message.chat.id,
                            parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
            count += 1
        bot.sendMessage(text=message[len(message) - 1], chat_id=update.callback_query.message.chat.id,
                        parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=reply_markup,
                        disable_web_page_preview=True)
    else:
        send_or_edit(bot, update, message[0], reply_markup)
    session.close()


def ShowVideoContent(bot, update, arg):
    CheckUser(bot, update)
    button_list = [
        [InlineKeyboardButton("🏠 Home", callback_data="0"), InlineKeyboardButton("🔍 Kurse", callback_data="1"),
         InlineKeyboardButton("📔 Dieser Kurs", callback_data="1$" + arg)]]
    reply_markup = InlineKeyboardMarkup(button_list)
    session = DBSession()
    entries = session.query(MMedia).filter(MMedia.course == arg).all()
    if len(entries) > 0:
        message = {
            0: "Videos zu [" + entries[0].coursedata.name + "](https://www.moodle.tum.de/course/view.php?id=" + str(
                entries[0].course) + "): \n"}
    else:
        message = {0: "Noch keine Videos vorhanden."}
    counter = 0
    for ent in sorted(entries, key=lambda x: x.date):
        toadd = "[" + ent.name + "](" + ent.playerurl + ")"
        if ent.mp4url1 is not None and ent.mp4url1 != "":
            toadd += " ([mp4](" + ent.mp4url1 + "))"
        if ent.mp4url2 is not None and ent.mp4url2 != "":
            toadd += ", ([mp4](" + ent.mp4url2 + "))\n"
        else:
            toadd += "\n"
        if len(message[counter] + toadd) > 4096:
            counter += 1
            message[counter] = toadd
        else:
            message[counter] += toadd
    if len(message) > 1:
        send_or_edit(bot, update, message[0], None)
        count = 1
        while count <= len(message) - 2:
            bot.sendMessage(text=message[count], chat_id=update.callback_query.message.chat.id,
                            parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
            count += 1
        bot.sendMessage(text=message[len(message) - 1], chat_id=update.callback_query.message.chat.id,
                        parse_mode=telegram.ParseMode.MARKDOWN, reply_markup=reply_markup,
                        disable_web_page_preview=True)
    else:
        send_or_edit(bot, update, message[0], reply_markup)
    session.close()


def Start(bot, update):
    usr = CheckUser(bot, update)
    ShowHome(bot, update, usr)


def ShowHome(bot, update, usr, text="🏠 Home"):
    button1 = InlineKeyboardButton("🛡️ Benachrichtigungen deaktivieren",
                                   callback_data="5$0") if usr.notifications else InlineKeyboardButton(
        "📡 Benachrichtigungen aktivieren", callback_data="5$1")
    button_list = [[button1], [InlineKeyboardButton("📆 Semester auswählen", callback_data="4")],
                   [InlineKeyboardButton("🔍 Kurse anzeigen", callback_data="1")]]
    reply_markup = InlineKeyboardMarkup(button_list)
    send_or_edit(bot, update, text, reply_markup)


def About(bot, update):
    CheckUser(bot, update)
    button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0")]]
    reply_markup = InlineKeyboardMarkup(button_list)
    bot.sendMessage(chat_id=update.message.chat_id,
                    text="Dieser Bot wurde erstellt von @Alwinius. Der Quellcode ist unter "
                         "https://github.com/Alwinius/tummoodlebot verfügbar.\nWeitere interessante Bots: \n - "
                         "@tummensabot\n - @mydealz_bot",
                    reply_markup=reply_markup)


def Fileupload(bot, update):
    usr = CheckUser(bot, update)
    if usr.id == int(config['DEFAULT']['AdminId']):
        if usr.current_selection >= 0:
            # Let's get started
            try:
                file_id = update.message.document.file_id
            except AttributeError:
                try:
                    file_id = update.message.photo[-1].file_id
                except AttributeError:
                    file_id = update.message.video.file_id
            # get the course
            session = DBSession()
            entry = session.query(CCourse).filter(CCourse.id == usr.current_selection).first()
            # send file to channel
            resp = bot.sendDocument(chat_id=config["DEFAULT"]["FilesChannelId"], document=file_id,
                                    caption=entry.name + " - " + update.message.caption)
            url = "https://t.me/" + config["DEFAULT"]["FilesChannelName"] + "/" + str(resp.message_id)
            new_file = FFile(id=entry.id, course=usr.current_selection, title=update.message.caption,
                             message_id=resp.message_id,
                             date=datetime.now(), url=url)
            session.add(new_file)
            session.commit()
            button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                            InlineKeyboardButton("📔 Dieser Kurs", callback_data="1$" + str(usr.current_selection))]]
            reply_markup = InlineKeyboardMarkup(button_list)
            message = "[" + entry.name + " - " + update.message.caption + "](" + url + ")"
            bot.sendMessage(chat_id=update.message.chat_id, text=message,
                            reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN,
                            disable_web_page_preview=True)
            session.close()
    else:
        button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0")]]
        reply_markup = InlineKeyboardMarkup(button_list)
        bot.sendMessage(chat_id=update.message.chat_id,
                        text="Du hast keine Berechtigung, Dateien hochzuladen" + str(usr.id),
                        reply_markup=reply_markup)


def AllInline(bot, update):
    args = update.callback_query.data.split("$")
    if int(args[0]) == 0:
        Start(bot, update)
    elif int(args[0]) == 1:
        if len(args) > 1:
            # Kursinhalte anzeigen
            ShowCourseContent(bot, update, args[1])
        else:
            # Kurs auswählen
            ShowCourses(bot, update)
    elif int(args[0]) == 4:
        # Semester auswählen oder speichern
        if len(args) > 1:
            SetSemester(bot, update)
        else:
            Semester(bot, update)
    elif int(args[0]) == 5 and len(args) > 1:
        # Benachrichtigungen ändern
        SetNotifications(bot, update, args[1])
    elif int(args[0]) == 6 and len(args) > 1:
        ShowVideoContent(bot, update, args[1])
    else:
        update.callback_query.message.reply_text("Kommando nicht erkannt")
        bot.sendMessage(text="Inlinekommando nicht erkannt.\n\nData: " + update.callback_query.data + "\n User: " + str(
            update.callback_query.message.chat), chat_id=config['DEFAULT']['AdminId'])


start_handler = CommandHandler('start', Start)
about_handler = CommandHandler('about', About)
dispatcher.add_handler(start_handler)
dispatcher.add_handler(about_handler)

inlinehandler = CallbackQueryHandler(AllInline)
dispatcher.add_handler(inlinehandler)

filehandler = MessageHandler(Filters.video | Filters.photo | Filters.document, Fileupload)
dispatcher.add_handler(filehandler)

fallbackhandler = MessageHandler(Filters.text, Start)
dispatcher.add_handler(fallbackhandler)

updater.start_webhook(listen='localhost', port=4214, webhook_url=config['DEFAULT']['WebHookUrl'])
updater.idle()
updater.stop()
