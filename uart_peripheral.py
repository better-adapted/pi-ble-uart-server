import sys
import dbus, dbus.mainloop.glib
from gi.repository import GLib
from example_advertisement import Advertisement
from example_advertisement import register_ad_cb, register_ad_error_cb
from example_gatt_server import Service, Characteristic
from example_gatt_server import register_app_cb, register_app_error_cb
from cobs import cobs

BLUEZ_SERVICE_NAME =           'org.bluez'
DBUS_OM_IFACE =                'org.freedesktop.DBus.ObjectManager'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
GATT_MANAGER_IFACE =           'org.bluez.GattManager1'
GATT_CHRC_IFACE =              'org.bluez.GattCharacteristic1'

STATUS_DUMMY = '{"command": "RS_MACHINE_STATUS","data": {"machineSerialNumber": "566GGHHHD","machineType": "Type 1","machineSettings": {"id": "ADEE669691","name": "default_settings","diameter": 10,"pulsesPerTurn": 100},"sensor": {"sensorSerialNumber": "5678"},"createdAt": "2025-05-07T15:33:06.149Z","updatedAt": "2025-05-07T15:33:06.149Z"}}'


# UART_RX_CHARACTERISTIC_UUID =  '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
# UART_TX_CHARACTERISTIC_UUID =  '6e400003-b5a3-f393-e0a9-e50e24dcca9e'
# LOCAL_NAME =                   'rpi-gatt-server'


# 59462f12-9543-9999-12c8-58b459a2712d
# 33333333-2222-2222-1111-111100000000
COBS_SERVICE_UUID =            '59462f12-9543-9999-12c8-58b459a2712d'
COBS_TXRX_CHARACTERISTIC_UUID =  '33333333-2222-2222-1111-111100000000'
COBS_LOCAL_NAME =             'VMA_1605'

NUS_SERVICE_UUID =            '6e400001-b5a3-f393-e0a9-e50e24dcca9e'
NUS_RX_CHARACTERISTIC_UUID =  '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
NUS_TX_CHARACTERISTIC_UUID =  '6e400003-b5a3-f393-e0a9-e50e24dcca9e'

NUS_LOCAL_NAME =              'NUS_1605'

mainloop = None

class COBS_TxRxCharacteristic(Characteristic):
    cobs_temp = cobs.encode(STATUS_DUMMY.encode()) + b"\x00"
    #cobs_temp = STATUS_DUMMY.encode()

    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, COBS_TXRX_CHARACTERISTIC_UUID, ['read','notify','write','write-without-response'], service)
        self.notifying = False
        GLib.io_add_watch(sys.stdin, GLib.IO_IN, self.on_console_input)

    def on_console_input(self, fd, condition):
        s = fd.readline()
        if s.isspace():
            pass
        else:
            self.send_tx(s)
        return True

    def send_tx(self, s):
        if not self.notifying:
            return
        value = []
        for c in s:
            value.append(dbus.Byte(c.encode()))
        self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': value}, [])

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False

    def ReadValue(self, options):
        return self.cobs_temp

    def WriteValue(self, value, options):
        self.zero_byte = b"\x00"
        print('remote: {}'.format(bytearray(value).decode()))
        temp = format(bytearray(value).decode())

        if (temp == '${"command":"MA_GET_MACHINE_STATUS"}\00') or temp == b"\x12":
            cobs_temp = cobs.encode(STATUS_DUMMY.encode()) + self.zero_byte
            self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': cobs_temp}, [])


class NUS_TxCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, NUS_TX_CHARACTERISTIC_UUID, ['notify'], service)
        self.notifying = False
        GLib.io_add_watch(sys.stdin, GLib.IO_IN, self.on_console_input)

    def on_console_input(self, fd, condition):
        s = fd.readline()
        if s.isspace():
            pass
        else:
            self.send_tx(s)
        return True

    def send_tx(self, s):
        if not self.notifying:
            return
        value = []
        for c in s:
            value.append(dbus.Byte(c.encode()))
        self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': value}, [])

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True

    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False

class NUS_RxCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, NUS_RX_CHARACTERISTIC_UUID,
                                ['write'], service)

    def WriteValue(self, value, options):
        print('remote: {}'.format(bytearray(value).decode()))

class NUS_Service(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, NUS_SERVICE_UUID, True)
        self.add_characteristic(NUS_TxCharacteristic(bus, 0, self))
        self.add_characteristic(NUS_RxCharacteristic(bus, 1, self))

class COBS_Service(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, COBS_SERVICE_UUID, True)
        self.add_characteristic(COBS_TxRxCharacteristic(bus, 0, self))

class Application(dbus.service.Object):
    def __init__(self, bus, path):
        self.path = path
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
        return response

class UartApplication(Application):
    def __init__(self, bus, path):
        Application.__init__(self, bus, path)
        self.add_service(NUS_Service(bus, 0))

class UartAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, 'peripheral')
        self.add_service_uuid(NUS_SERVICE_UUID)
        self.add_local_name(NUS_LOCAL_NAME)
        self.include_tx_power = True

class CobsApplication(Application):
    def __init__(self, bus, path):
        Application.__init__(self, bus, path)
        self.add_service(COBS_Service(bus, 1))

class CobsAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, 'peripheral')
        self.add_service_uuid(COBS_SERVICE_UUID)
        self.add_local_name(COBS_LOCAL_NAME)
        self.include_tx_power = True

def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                               DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for o, props in objects.items():
        if LE_ADVERTISING_MANAGER_IFACE in props and GATT_MANAGER_IFACE in props:
            return o
        print('Skip adapter:', o)
    return None

def main():
    global mainloop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = find_adapter(bus)
    if not adapter:
        print('BLE adapter not found')
        return

    service_manager = dbus.Interface(
                                bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                LE_ADVERTISING_MANAGER_IFACE)

    #nus_app = UartApplication(bus,'/nus')
    #nus_adv = UartAdvertisement(bus, 0)
    #service_manager.RegisterApplication(nus_app.get_path(), {},reply_handler=register_app_cb,error_handler=register_app_error_cb)
    #ad_manager.RegisterAdvertisement(nus_adv.get_path(), {},reply_handler=register_ad_cb,error_handler=register_ad_error_cb)

    cobs_app = CobsApplication(bus,'/')
    cobs_adv = CobsAdvertisement(bus, 0)
    service_manager.RegisterApplication(cobs_app.get_path(), {},reply_handler=register_app_cb,error_handler=register_app_error_cb)
    ad_manager.RegisterAdvertisement(cobs_adv.get_path(), {},reply_handler=register_ad_cb,error_handler=register_ad_error_cb)

    mainloop = GLib.MainLoop()

    try:
        mainloop.run()
    except KeyboardInterrupt:
        cobs_adv.Release()

if __name__ == '__main__':
    main()
