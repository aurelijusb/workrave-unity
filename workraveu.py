#!/usr/bin/python

########################################################################
# Program reminds to take regular breaks during the work.              #
#                                                                      #
# Port of well known WorkRave program to use all functionality of      #
# Unity environment                                                    #
########################################################################
#
# State machine:
#
#     +------[Take a break]--+
#     |                      V
# Working --> Switching --> Break --> Back-to-Work
#  ^  ^        |  ^            |          |      
#  |  +-[Skip]-+  +-[Postpone]-+          |
#  |                                      |
#  +--------------------------------------+
#
#
# Variables:
#  self.timer - seconds from work start to break start
#  self.break_timer - seconds from break start to work start
#
# Author: Aurelijus Banelis
__version__ = "$Revision: 7 $"


import ConfigParser
import os.path
import math
import time
import datetime

#~ from gi.repository import Unity, Gio, Dbusmenu
import appindicator
import pynotify
import gtk
import gtk.glade
import gobject
import signal
import pygame

class WorkRaveUnity:
    STATE_WORKING = 0
    STATE_BREAK = 1
    STATE_POSPONE = 3
    STATE_CLOSE = 4

    SECOND = 1000


    #
    # Initialization
    #

    def main(self):
        self.config_init()
        self.indicators_init()
        self.reset_timer()
        self.window_init()
        gtk.main()


    #
    # Configurations and commons
    #

    def config_init(self):
        self.config = ConfigParser.RawConfigParser()
        self.config_dir = os.path.expanduser("~/.workrave-unity")
        self.file = os.path.realpath(self.config_dir + "/settings.ini")
        if (not os.path.isdir(self.config_dir)):
            os.makedirs(self.config_dir)
                        
        if (os.path.isfile(self.file)):
            self.config.read(self.file)
        else:
            self.config.add_section("Micro-break")
            self.config.add_section("Application")
            self.config.add_section("Logging")
            self.config.add_section("Sounds")
            self.config_default()
            self.config_save(self.file)
        self.count = int(self.config.get("Micro-break", "work-mintes")) * 60


    def config_default(self):
        self.config.set("Micro-break", "work-mintes", '45')
        self.config.set("Micro-break", "postpone-mintes", '5')
        self.config.set("Micro-break", "break-mintes", '10')

        self.config.set("Application", "version", '0.1')

        self.config.set("Logging", "log-time", 'True')
        self.config.set("Logging", "log-dir", '/log/%Y/%Y-%m-%d.log')

        self.config.set("Sounds", "back-to-work", '/usr/share/sounds/ubuntu/stereo/system-ready.ogg')

    def config_save(self, file=None):
        if (file is None):
            file = self.file
        with open(file, 'wb+') as configfile:
            self.config.write(configfile)   


    def date_to_string(self, seconds):
        if (seconds > 60):
            return "%d min %d s." % (math.floor(seconds / 60), seconds%60)
        else:
            return "%d s." % seconds
        #TODO: mins min, hours

    def quit(self, widget=None, args=None):
        self.config_save()
        self.change_state(self.STATE_CLOSE)
        gtk.main_quit()


    def change_state(self, state):
        self.state = state
        self.log_state(state)


    def log_state(self, state):
        if (self.config.get("Logging", "log-time") == "True"):
            now = datetime.datetime.now()
            log_file = self.config_dir + now.strftime(
                                         self.config.get("Logging", "log-dir"))
            log_dir = os.path.dirname(log_file)
            if (not os.path.isdir(log_dir)):
                os.makedirs(log_dir)
            file = open(log_file, 'a')
            time = now.strftime("%Y-%m-%d %H:%M:%S")
            if (state == self.STATE_CLOSE):
                file.write(time + " Closing\n")
            elif (state == self.STATE_WORKING):
                file.write(time + " Working\n")
            elif (state == self.STATE_POSPONE):
                file.write(time + " Posponed\n")
            else:
                file.write(time + " Break\n")
            file.close()

    #
    # Indicators and GUI
    #

    def indicators_init(self):
        pynotify.init ("workraveu")             #TODO: capbilities - pynotify.get_server_caps()
        #~ self.launcher = Unity.LauncherEntry.get_for_desktop_id(
                                            #~ "workraveu.desktop")

        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.resources_dir = current_dir + "/res";
        default_icon = self.resources_dir + "/icon-16.png"
        self.indicator = appindicator.Indicator ("workraveu", default_icon,
                                      appindicator.CATEGORY_APPLICATION_STATUS)

        menu = gtk.Menu()
        self.menu_timer = gtk.MenuItem("Starting timer")
        self.menu_timer.connect_object('activate', self.force_break, None)
        self.menu_timer.show()
        menu.append(self.menu_timer)

        self.menu_pospone = gtk.MenuItem("Skip break")
        self.menu_pospone.connect_object('activate', self.force_skip, None)
        menu.append(self.menu_pospone)

        quit_menu = gtk.MenuItem("Quit")
        quit_menu.connect_object("activate", gtk.main_quit, None)
        quit_menu.show()
        menu.append(quit_menu)              #TODO: Preferences, silent mode, statistics

        self.indicator.set_menu(menu)


    def window_init(self):
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("Workrave Unity")
        self.window.connect("delete_event", self.quit)
        self.window.connect("destroy", self.quit)
        self.window.set_border_width(2)
        self.window.stick()
        self.window.set_keep_above(True)

        hbox = gtk.HBox(True, 4)

        self.button_break = gtk.Button("Take a break")
        self.button_break.connect_object("clicked", self.force_break, None)
        hbox.add(self.button_break)
        self.button_break.show()

        self.button_postpone = gtk.Button("Postpone break")
        self.button_postpone.connect_object("clicked", self.force_postpone, None)
        hbox.add(self.button_postpone)

        self.button_work = gtk.Button("Back to work")
        self.button_work.connect_object("clicked", self.back_to_work, None)
        hbox.add(self.button_work)

        vbox = gtk.VBox(False, 2)
        self.break_progress = gtk.ProgressBar()
        self.break_progress.set_size_request(200,20)
        vbox.add(self.break_progress)
        vbox.add(hbox)
        vbox.show()
        hbox.show()
        self.window.add(vbox)

        e = gtk.Entry()
        map = e.get_colormap()
        colour = map.alloc_color("#000000")
        colour_grey = map.alloc_color("#1A1A1A")
        fore_colour = map.alloc_color("#FFFFFF")

        self.default_style = e.get_style()
        self.black = self.default_style.copy()
        self.black.bg[gtk.STATE_NORMAL] = colour
        self.black.bg[gtk.STATE_ACTIVE] = colour
        self.black.bg[gtk.STATE_SELECTED] = colour
        self.black.bg[gtk.STATE_INSENSITIVE] = colour
        self.black.bg[gtk.STATE_PRELIGHT] = colour
        self.black.fg[gtk.STATE_NORMAL] = fore_colour
        self.black.fg[gtk.STATE_ACTIVE] = fore_colour
        self.black.fg[gtk.STATE_SELECTED] = fore_colour
        self.black.fg[gtk.STATE_INSENSITIVE] = fore_colour
        self.black.fg[gtk.STATE_PRELIGHT] = fore_colour
        
        self.grey = self.black.copy()
        self.grey.bg[gtk.STATE_PRELIGHT] = colour_grey

        self.window.set_style(self.black)
        self.break_progress.set_style(self.grey)


    #
    # Working (counting to next break)
    #
          
    def force_skip(self, widget=None, args=None):
        self.reset_timer(timer=0, renewTimer=False)
        self.menu_pospone.hide();
        self.log_state(self.STATE_POSPONE)
        self.window.hide()
          
    def reset_timer(self, timer=0, renewTimer=True):
        self.timer = timer
        self.break_timer = 0
        self.change_state(self.STATE_WORKING)
        if (renewTimer):
            self.timer_id = gobject.timeout_add(self.SECOND, self.timer_update)

    def timer_update(self):
        if (self.state != self.STATE_WORKING):
            return False
        
        if (self.timer == None):
            self.timer = 1
        else:
            self.timer += 1
        self.menu_timer.set_label("Till next break: %s" %
                                  self.date_to_string(self.count - self.timer));
        postpone_time = int(self.config.get("Micro-break",
                                            "postpone-mintes")) * 60

        if (self.timer == self.count):
            self.indicate_brake()
        elif (self.timer - self.count > postpone_time):
            self.force_break()
            return False
        else:
            self.work_update()
        return True;

    def work_update(self):
        percent = int(self.timer / float(self.count) * 5) * 20
        if (percent == 0):
            percent = '';
        else:
            percent = '-' + str(percent)
        icon = self.resources_dir + "/icon-16" + percent + ".png"
        self.indicator.set_status (appindicator.STATUS_ATTENTION)
        self.indicator.set_attention_icon(icon)


    #
    # Switching to break state
    #

    def force_postpone(self, widget=None, args=None):
        time = int(self.config.get("Micro-break", "work-mintes")) * 60 + 1
        self.reset_timer(time)
        self.switching_update()
        max_break = int(self.config.get("Micro-break", "break-mintes")) * 60
        self.break_timer = max_break + 1            #TODO: beter way to stop timer


    def switching_update(self):
        postpone_seconds = int(self.config.get("Micro-break",
                                               "postpone-mintes")) * 60
        till_force = postpone_seconds - (self.timer - self.count)
        #~ self.launcher.set_property("count", till_force)
        #~ self.launcher.set_property("count_visible", True)
        #~ self.launcher.set_property("progress", postpone_seconds - till_force)
        #~ self.launcher.set_property("progress_visible", True)

        self.button_break.show()
        self.button_postpone.hide()
        self.button_work.hide()
        self.break_progress.hide()

        self.window.unfullscreen()
        self.window.resize(200, 100)
        self.window.show()

        if (self.timer % 30 == 0):
            self.indicate_brake(True)
            #~ self.launcher.set_property("urgent", True)


    def indicate_brake(self, urgent=False):
        self.indicator.set_status (appindicator.STATUS_ACTIVE)
        icon = self.resources_dir + "/icon-16-100.png"
        if (urgent):
            icon = self.resources_dir + "/icon-16-120.png"
        self.indicator.set_icon (icon)
        nofitfication = pynotify.Notification ("Work Rave",
                                               "You should take a break", icon)
        nofitfication.show()
        self.menu_pospone.show()


    #
    # Break
    #

    def force_break(self, widget=None, args=None):
        self.button_break.hide()
        self.button_work.hide()
        self.break_progress.show()
        self.button_postpone.show()
        self.break_timer = 0
        self.change_state(self.STATE_BREAK)
        self.break_timer_id = gobject.timeout_add(self.SECOND, self.break_timer_update)
        
        self.window.set_style(self.black)
        self.button_postpone.set_style(self.black)
        self.window.fullscreen()
        self.window.stick()
        self.window.set_keep_above(True)
        self.window.show()
        


    def break_timer_update(self):
        if (self.state != self.STATE_BREAK):
            return False

        self.break_timer += 1
        max_break = int(self.config.get("Micro-break", "break-mintes")) * 60
        if (self.break_timer < max_break):
            self.break_progress.set_fraction(1 - self.break_timer /
                                                 float(max_break))
            self.break_progress.set_text(self.date_to_string(max_break -
                                                             self.break_timer))
            self.break_progress.show()
            return True
        else:
            self.break_progress.hide()
            self.button_postpone.hide()
            self.button_work.show()
            self.play_sound(self.config.get("Sounds", "back-to-work"))
            return False


    def back_to_work(self, widget=None, args=None):
        self.window.hide()
        self.menu_pospone.hide()
        self.reset_timer()

    def play_sound(self, file):
        if (os.path.isfile(file)):
            pygame.init()
            sound = pygame.mixer.Sound(file)
            sound.play()



if __name__ == "__main__":
    base = WorkRaveUnity()
    try:
        base.main()
    except KeyboardInterrupt:
        base.change_state(base.STATE_CLOSE)
