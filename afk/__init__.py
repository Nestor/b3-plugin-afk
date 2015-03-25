# -*- encoding: utf-8 -*-
#
# AFK Plugin for BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2015 Thomas LEVEIL <thomasleveil@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
from ConfigParser import NoOptionError
from threading import Timer
from time import time
from b3 import TEAM_SPEC
from b3.plugin import Plugin
from weakref import WeakKeyDictionary

__author__ = "Thomas LEVEIL"
__version__ = "1.3"


class AfkPlugin(Plugin):
    def __init__(self, console, config=None):
        """
        Build the plugin object.
        """
        Plugin.__init__(self, console, config)

        self.MIN_INGAME_PLAYERS = 1

        """:type : int"""
        self.check_frequency_second = 0

        """:type : int"""
        self.inactivity_threshold_second = None

        """:type : int"""
        self.last_chance_delay = 15

        """:type : str"""
        self.kick_reason = None

        """:type : str"""
        self.are_you_afk = None

        """:type : Timer"""
        self.immunity_level = 100

        """:type : int"""
        self.check_timer = None

        """:type : dict[Client, threading.Timer]"""
        self.kick_timers = WeakKeyDictionary()

    def onStartup(self):
        """
        Initialize plugin.
        """
        self.registerEvent(self.console.getEventID('EVT_CLIENT_JOIN'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_TEAM_CHANGE'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_TEAM_CHANGE2'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_SAY'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_TEAM_SAY'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_SQUAD_SAY'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_PRIVATE_SAY'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_KILL'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_GIB'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_GIB_TEAM'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_GIB_SELF'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_SUICIDE'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_KILL_TEAM'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_DAMAGE'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_DAMAGE_SELF'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_DAMAGE_TEAM'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_ITEM_PICKUP'), self.on_client_activity)
        self.registerEvent(self.console.getEventID('EVT_CLIENT_ACTION'), self.on_client_activity)

        self.registerEvent(self.console.getEventID('EVT_CLIENT_DISCONNECT'), self.on_client_disconnect)
        self.registerEvent(self.console.getEventID('EVT_GAME_ROUND_START'), self.on_game_break)
        self.registerEvent(self.console.getEventID('EVT_GAME_ROUND_END'), self.on_game_break)
        self.registerEvent(self.console.getEventID('EVT_GAME_WARMUP'), self.on_game_break)
        self.registerEvent(self.console.getEventID('EVT_GAME_MAP_CHANGE'), self.on_game_break)

    def onEnable(self):
        self.start_check_timer()

    def onDisable(self):
        self.info("stopping timers")
        self.stop_check_timer()
        self.stop_kick_timers()

    ####################################################################################################################
    #                                                                                                                  #
    #   CONFIG                                                                                                         #
    #                                                                                                                  #
    ####################################################################################################################

    def onLoadConfig(self):
        self.load_conf_check_frequency()
        self.load_conf_inactivity_threshold()
        self.load_conf_kick_reason()
        self.load_conf_are_you_afk()
        self.load_conf_immunity_level()

        self.stop_check_timer()
        self.stop_kick_timers()
        self.start_check_timer()

    def load_conf_check_frequency(self):
        try:
            self.check_frequency_second = int(60 * self.config.getDuration('settings', 'check_frequency'))
            self.info('settings/check_frequency: %s sec' % self.check_frequency_second)
        except (NoOptionError, ValueError), err:
            self.warning("No value or bad value for settings/check_frequency. %s", err)
            self.check_frequency_second = 0
        else:
            if self.check_frequency_second < 0:
                self.warning("settings/check_frequency cannot be less than 0")
                self.check_frequency_second = 0

    def load_conf_inactivity_threshold(self):
        try:
            self.inactivity_threshold_second = int(60 * self.config.getDuration('settings', 'inactivity_threshold'))
            self.info('settings/inactivity_threshold: %s sec' % self.inactivity_threshold_second)
        except (NoOptionError, ValueError), err:
            self.warning("No value or bad value for settings/inactivity_threshold. %s", err)
            self.inactivity_threshold_second = 0
        else:
            if self.inactivity_threshold_second < 30:
                self.warning("settings/inactivity_threshold cannot be less than 30 sec")
                self.inactivity_threshold_second = 30

    def load_conf_kick_reason(self):
        try:
            self.kick_reason = self.config.get('settings', 'kick_reason')
            if len(self.kick_reason.strip()) == 0:
                raise ValueError()
            self.info('settings/kick_reason: %s sec' % self.kick_reason)
        except (NoOptionError, ValueError), err:
            self.warning("No value or bad value for settings/kick_reason. %s", err)
            self.kick_reason = "AFK for too long on this server"

    def load_conf_are_you_afk(self):
        try:
            self.are_you_afk = self.config.get('settings', 'are_you_afk')
            if len(self.are_you_afk.strip()) == 0:
                raise ValueError()
            self.info('settings/are_you_afk: %s sec' % self.are_you_afk)
        except (NoOptionError, ValueError), err:
            self.warning("No value or bad value for settings/are_you_afk. %s", err)
            self.are_you_afk = "Are you AFK?"

    def load_conf_immunity_level(self):
        try:
            self.immunity_level = self.config.getint('settings', 'immunity_level')
        except NoOptionError:
            self.info('No value for settings/immunity_level. Using default value : %s' % self.immunity_level)
        except ValueError, err:
            self.debug(err)
            self.warning('Bad value for settings/immunity_level. Using default value : %s' % self.immunity_level)
        except Exception, err:
            self.error(err)
        self.info('immunity_level is %s' % self.immunity_level)

    ####################################################################################################################
    #                                                                                                                  #
    #   EVENTS                                                                                                         #
    #                                                                                                                  #
    ####################################################################################################################

    def on_client_disconnect(self, event):
        """
        make sure to clean eventual timers when a client disconnects

        :param event: b3.events.Event
        """
        self.clear_kick_timer_for_client(event.client)
        delattr(event.client, "last_activity_time")

    def on_client_activity(self, event):
        """
        update Client.last_activity_time.

        :param event: b3.events.Event
        """
        if not event.client:
            return
        if event.client in self.kick_timers:
            event.client.message("OK, you are not AFK")
        event.client.last_activity_time = time()
        self.clear_kick_timer_for_client(event.client)

    def on_game_break(self, _):
        """
        Clear all last activity records so no one can be kick before he has time to join the game.
        This is to prevent player with slow computer to get kicked while loading the map at round start.

        """
        self.info("game break, clearing afk timers")
        self.stop_kick_timers()
        for client in [x for x in self.console.clients.getList() if hasattr(x, 'last_activity_time')]:
            del client.last_activity_time

    ####################################################################################################################
    #                                                                                                                  #
    #   OTHERS                                                                                                         #
    #                                                                                                                  #
    ####################################################################################################################

    def search_for_afk(self):
        """
        check all connected players who are not in the spectator team for inactivity.
        """
        list_of_players = [x for x in self.console.clients.getList()
                           if x.team != TEAM_SPEC and
                           not getattr(x, 'bot', False)
                           ]
        if len(list_of_players) <= self.MIN_INGAME_PLAYERS:
            self.verbose("too few players in game, skipping AFK check")
        else:
            self.verbose2("looking for afk players...")
            for client in list_of_players:
                self.check_client(client)
        self.start_check_timer()

    def check_client(self, client):
        """
        check if client is afk
        :param client: b3.clients.Client
        """
        if self.is_client_inactive(client):
            self.ask_client(client)

    def is_client_inactive(self, client):
        if getattr(client, 'bot', False):
            self.verbose2("%s is a bot" % client.name)
            return False
        if client.maxLevel >= self.immunity_level:
            self.verbose2("%s is in group %s -> immune" % (client.name, client.maxGroup))
            return False
        if client.team in (TEAM_SPEC,):
            self.verbose2("%s is in %s team" % (client.name, client.team))
            return False
        if not hasattr(client, 'last_activity_time'):
            self.verbose2("%s has no last activity time recorded, cannot check" % client.name)
            return False
        inactivity_duration = time() - client.last_activity_time
        self.verbose2("last activity for %s was %0.1fs ago" % (client.name, inactivity_duration))
        return inactivity_duration > self.inactivity_threshold_second

    def ask_client(self, client):
        """
        ask a player if he is afk.

        :param client : b3.clients.Client
        """
        if client in self.kick_timers:
            self.verbose("%s is already in kick_timers" % client)
            return
        client.message(self.are_you_afk)
        self.console.say("%s suspected of being AFK, kicking in %ss if no answer"
                         % (client.name, self.last_chance_delay))
        t = Timer(self.last_chance_delay, self.kick, (client, ))
        t.start()
        self.kick_timers[client] = t

    def kick(self, client):
        """
        kick a player after showing a message on the server
        :param client: the player to kick
        """
        if self.is_client_inactive(client):
            self.console.say("kicking %s: %s" % (client.name, self.kick_reason))
            client.kick(reason=self.kick_reason)

    def start_check_timer(self):
        """
        start a timer for the next check
        """
        if self.check_frequency_second > 0:
            if self.check_timer:
                self.check_timer.cancel()
            self.check_timer = Timer(self.check_frequency_second, self.search_for_afk)
            self.check_timer.start()

    def stop_check_timer(self):
        if self.check_timer:
            self.check_timer.cancel()

    def stop_kick_timers(self):
        if self.kick_timers:
            for client in list(self.kick_timers.keys()):
                timer = self.kick_timers.pop(client)
                if timer:
                    timer.cancel()

    def clear_kick_timer_for_client(self, client):
        if self.kick_timers:
            if client in self.kick_timers:
                self.kick_timers.pop(client).cancel()
                self.info("cancelling pending kick for %s" % client)

    def verbose2(self, msg, *args, **kwargs):
        """
        Log a VERBOSE2 message to the main log. More "chatty" than a VERBOSE message.
        """
        self.console.verbose2('%s: %s' % (self.__class__.__name__, msg), *args, **kwargs)