#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
#  Please note that any incorrect or careless usage of this module as well as errors in the implementation can damage your hardware!
#  Therefore, the author does not provide any guarantee or warranty concerning to correctness, functionality or performance and does not accept any liability for damage caused by this module, examples or mentioned information.
#  Thus, use it at your own risk!
#
#  Based on the documentation provided by Kostal:
#
import pymodbus
import sys
sys.path.insert(1, '/data/etc/vebus')
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from vedbus import VeDbusService
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib as gobject  # Python 3.x
import dbus
import dbus.service
import os
import platform
import configparser # for config/ini file
import collections
import logging

# our own packages
#sys.path.insert(1, os.path.join(os.path.dirname(__file__), '/opt/victronenergy/dbus-modem'))

# Again not all of these needed this is just duplicating the Victron code.
class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM)

class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)

def dbusconnection():
    return SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else SystemBus()

# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
DBusGMainLoop(set_as_default=True)

class kostal_modbusquery:
    def __init__(self):
        #Change the IP address and port to suite your environment:
        self.grid_ip=config['MODBUS']['ipaddress']
        self.grid_port=config['MODBUS']['port']
        self.Adr = collections.OrderedDict()
        self.Adr[14] = [14,"Inverter serial number","Str8",0]
        self.Adr[38] = [38,"Software-Version Maincontroller (MC)","Str8",0]
        self.Adr[154] = [154,"Current L1","R32",0]
        self.Adr[156] = [156,"Active power L1","R32",0]
        self.Adr[158] = [158,"Voltage L1","R32",0]
        self.Adr[160] = [160,"Current L2","R32",0]
        self.Adr[162] = [162,"Active power L2","R32",0]
        self.Adr[164] = [164,"Voltage L2","R32",0]
        self.Adr[166] = [166,"Current L3","R32",0]
        self.Adr[168] = [168,"Active power L3","R32",0]
        self.Adr[170] = [170,"Voltage L3","R32",0]
        self.Adr[172] = [172,"Total AC active power","R32",0]
        self.Adr[320] = [320,"Total yield","R32",0]

    # Routine to read a Float from one address with 2 registers
    def ReadFloat(self, myadr_dec):
        r1 = self.client.read_holding_registers(myadr_dec, 2, unit=71)
        FloatRegister = BinaryPayloadDecoder.fromRegisters(
            r1.registers, byteorder=Endian.Big, wordorder=Endian.Little)
        result_FloatRegister = round(FloatRegister.decode_32bit_float(), 2)
        return(result_FloatRegister)
    # -----------------------------------------

    # Routine to read a string from one address with 8 registers
    def ReadStr8(self, myadr_dec):
        r1 = self.client.read_holding_registers(myadr_dec, 8, unit=71)
        STRG8Register = BinaryPayloadDecoder.fromRegisters(
            r1.registers, byteorder=Endian.Big)
        result_STRG8Register = STRG8Register.decode_string(8)
        result_STRG8Register = bytes(filter(None,result_STRG8Register))    #Get rid of the "\X00"s
        return(result_STRG8Register)
    # -----------------------------------------

    try:
        def run(self):
            self.client = ModbusTcpClient(self.grid_ip, port=self.grid_port)
            self.client.connect()
            
            for key in self.Adr:
                dtype = self.Adr[key][2]
                if dtype == "Str8":
                    reader = self.ReadStr8
                elif dtype == "R32":
                    reader = self.ReadFloat
                else:
                    raise ValueError("Data type not known: %s"%dtype)

                val = reader(key)
                self.Adr[key][3] = val

            self.client.close()
            
            # pvinverter
            
            dbusservice['pvinverter.kostal']['/Ac/L1/Current'] = self.Adr[154][3]
            dbusservice['pvinverter.kostal']['/Ac/L2/Current'] = self.Adr[160][3]
            dbusservice['pvinverter.kostal']['/Ac/L3/Current'] = self.Adr[166][3]

            dbusservice['pvinverter.kostal']['/Ac/L1/Voltage'] = self.Adr[158][3]
            dbusservice['pvinverter.kostal']['/Ac/L2/Voltage'] = self.Adr[164][3]
            dbusservice['pvinverter.kostal']['/Ac/L3/Voltage'] = self.Adr[170][3]

            dbusservice['pvinverter.kostal']['/Ac/L1/Power'] = self.Adr[156][3]
            dbusservice['pvinverter.kostal']['/Ac/L2/Power'] = self.Adr[162][3]
            dbusservice['pvinverter.kostal']['/Ac/L3/Power'] = self.Adr[168][3]

            dbusservice['pvinverter.kostal']['/Ac/L1/Energy/Forward'] = self.Adr[320][3]/3000.0
            dbusservice['pvinverter.kostal']['/Ac/L2/Energy/Forward'] = self.Adr[320][3]/3000.0
            dbusservice['pvinverter.kostal']['/Ac/L3/Energy/Forward'] = self.Adr[320][3]/3000.0

            dbusservice['pvinverter.kostal']['/Ac/Energy/Forward'] = self.Adr[320][3]/1000.0
            dbusservice['pvinverter.kostal']['/Ac/Power'] = self.Adr[172][3]
            dbusservice['pvinverter.kostal']['/Ac/MaxPower'] = 7000


    except Exception as ex:
        logging.error("ERROR: Hit the following error :From subroutine kostal_modbusquery.run() : %s" % ex)
    # -----------------------------

    try:
        def updateStaticInformations(self):
            self.client = ModbusTcpClient(self.grid_ip, port=self.grid_port)
            self.client.connect() 
            logging.info("MODBUS client: Update static Informations")

            for key in self.Adr:
                dtype = self.Adr[key][2]
                if dtype == "Str8":
                    reader = self.ReadStr8
                elif dtype == "R32":
                    reader = self.ReadFloat
                else:
                    raise ValueError("Data type not known: %s"%dtype)

                val = reader(key)
                self.Adr[key][3] = val

            self.client.close()
            
            # pvinverter
            dbusservice['pvinverter.kostal']['/Serial'] = self.Adr[14][3].decode('UTF-8')
            dbusservice['pvinverter.kostal']['/FirmwareVersion'] = self.Adr[38][3].decode('UTF-8')

    except Exception as ex:
        logging.error("ERROR: Hit the following error :From subroutine kostal_modbusquery.updateStaticInformations() : %s" % ex)
    # -----------------------------
# Here is the bit you need to create multiple new services - try as much as possible timplement the Victron Dbus API requirements.

def new_service(base, type, physical, id, instance, config):
    self = VeDbusService("{}.{}.{}_id{:02d}".format(
        base, type, physical,  id), dbusconnection())

    def gettextforkWh(path, value): return ("%.1FkWh" % (float(value)))
    def gettextforW(path, value): return ("%.0FW" % (float(value)))
    def gettextforV(path, value): return ("%.0FV" % (float(value)))
    def gettextforA(path, value): return ("%.1FA" % (float(value)))

    # Create the management objects, as specified in the ccgx dbus-api document
    self.add_path('/Mgmt/ProcessName', __file__)
    self.add_path('/Mgmt/ProcessVersion','1.0')
    self.add_path('/Mgmt/Connection','Modbus TCP')
    self.add_path('/Connected', 1)
    self.add_path('/HardwareVersion', 0)
    #self.add_path('/Serial', "1")
    self.add_path('/Ac/L1/Voltage', None, gettextcallback=gettextforV)
    self.add_path('/Ac/L2/Voltage', None, gettextcallback=gettextforV)
    self.add_path('/Ac/L3/Voltage', None, gettextcallback=gettextforV)
    self.add_path('/Ac/L1/Current', None, gettextcallback=gettextforA)
    self.add_path('/Ac/L2/Current', None, gettextcallback=gettextforA)
    self.add_path('/Ac/L3/Current', None, gettextcallback=gettextforA)
    self.add_path('/Ac/L1/Power', None, gettextcallback=gettextforW)
    self.add_path('/Ac/L2/Power', None, gettextcallback=gettextforW)
    self.add_path('/Ac/L3/Power', None, gettextcallback=gettextforW)
    self.add_path('/Ac/Power', None, gettextcallback=gettextforW)
    self.add_path('/Ac/L1/Energy/Forward', None, gettextcallback=gettextforkWh)
    self.add_path('/Ac/L2/Energy/Forward', None, gettextcallback=gettextforkWh)
    self.add_path('/Ac/L3/Energy/Forward', None, gettextcallback=gettextforkWh)
    
    # Create device type specific objects
    if type == 'pvinverter.kostal':
        self.add_path('/CustomName', config['DEFAULT']['name'])
        self.add_path('/DeviceInstance', instance)
        self.add_path('/FirmwareVersion', None)
        self.add_path('/Serial', None)
        # value used in ac_sensor_bridge.cpp of dbus-cgwacs
        self.add_path('/ProductId', 41284)
        self.add_path('/ProductName', "Kostal Plenticore Plus")
        self.add_path('/Ac/MaxPower', None, gettextcallback=gettextforW)
        self.add_path('/Ac/Energy/Forward', None, gettextcallback=gettextforkWh)
        self.add_path('/ErrorCode', None)
        self.add_path('/Position', int(config['DEFAULT']['position']))
        self.add_path('/StatusCode', 0)
    return self

def _run():
    try:
        Kostalquery = kostal_modbusquery()
        Kostalquery.run()
    except Exception as ex:
        logging.error("MODBUS: Error in run(): %s" % ex)
    return True

def _updateStaticInformations():
    try:
        Kostalquery = kostal_modbusquery()
        Kostalquery.updateStaticInformations()
    except Exception as ex:
        logging.error("MODBUS: Error in _updateStaticInformations(): %s" % ex)
    return True

try:
    config = configparser.ConfigParser()
    config.read("%s/config.ini" % (os.path.dirname(os.path.realpath(__file__))))
    if (config['MODBUS']['ipaddress'] == "IP_ADDR"):
        print("ERROR: config.ini file is using invalid default values like IP_ADDR. The driver restarts in 60 seconds.")
        time.sleep(60)
        sys.exit()
except:
    print("ERROR: config.ini file not found. Copy or rename the config.sample.ini to config.ini. The driver restarts in 60 seconds.")
    time.sleep(60)
    sys.exit()

# Get logging level from config.ini
# ERROR = shows errors only
# WARNING = shows ERROR and warnings
# INFO = shows WARNING and running functions
# DEBUG = shows INFO and data/values
if 'DEFAULT' in config and 'logging' in config['DEFAULT']:
    if config['DEFAULT']['logging'] == 'DEBUG':
        logging.basicConfig(level=logging.DEBUG)
    elif config['DEFAULT']['logging'] == 'INFO':
        logging.basicConfig(level=logging.INFO)
    elif config['DEFAULT']['logging'] == 'ERROR':
        logging.basicConfig(level=logging.ERROR)
    else:
        logging.basicConfig(level=logging.WARNING)
else:
    logging.basicConfig(level=logging.WARNING)

dbusservice = {}  # Dictonary to hold the multiple services

# service defined by (base*, type*, id*, instance):
# * items are include in service name
# Create all the dbus-services we want
dbusservice['pvinverter.kostal'] = new_service("com.victronenergy", 'pvinverter.kostal', 'pvinverter', 0, 20, config)

# Everything done so just set a time to run an update function to update the data values every x second
_updateStaticInformations()
gobject.timeout_add((1000 / int(config['DEFAULT']['freqency'])), _run)
#gobject.timeout_add(60000, _updateStaticInformations)

logging.info("Connected to dbus, and switching over to gobject.MainLoop() (= event based)")
mainloop = gobject.MainLoop()
mainloop.run()

#if __name__ == "__main__":
#    try:
#        Kostalquery = kostal_modbusquery()
#        Kostalquery.run()
#    except Exception as ex:
#        print("Issues querying KSEM -ERROR :", ex)
