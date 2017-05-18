#!/usr/bin/env python3
try:
    import serial
except ImportError as e:
    print("Error: Please install pyserial")
    print(e.__str__())
    exit(1)
import sys
import telnetlib
import string
import socket
import threading
import argparse
from time import sleep

###########
# Globals #
###########

exit_flag = 0

#############
# Functions #
#############


def serial_try():
    chamber_control_name = "thermal8-wkst"
    portNumber = "7777"

    try:
        tn = telnetlib.Telnet(host = chamber_control_name,
            port = portNumber,
            timeout = 5)
    except socket.timeout as e:
        print("Timed out connecting to {} on port {}, verify it is awake.")
        exit(1)

    writefile = open("something.txt", "w")
    blah = ""
    while 1:
        blah = blah + tn.read_some().decode("ascii").strip()
        if "[ press 'Q' to qui" in blah:
            print("writing some stuffs")
            blah = blah.replace("[K[33m", "")
            blah = blah.replace("[0;10m[32m[1m", "")
            blah = blah.replace("[K", "")
            blah = blah.replace("[0;10m", "")
            blah = blah.replace("[K[1;1H[33m", "\n")
            blah = blah.replace("[1;1H[33m", "\n")
            writefile.write(blah+"\n")
            blah = ""
    writefile.close()
    tn.close()

#Function for handling connections. This will be used to create threads
def clientthread(conn):
    #Sending message to connected client
    conn.send('Welcome to the server. Type something and hit enter\n'.encode("ascii")) #send only takes string
     
    #infinite loop so that function do not terminate and thread do not end.
    while True:
         
        #Receiving from client
        data = conn.recv(1024)
        data = data.decode("ascii")
        reply = ('\tOK...' + data).encode("unicode_escape")
        
        if not data.strip(): 
            break
     
        conn.sendall(reply)
     
    #came out of loop
    conn.close()

###########
# Classes #
###########

class netToSerThread(threading.Thread):
    def __init__(self, conn, net_threads, net_lock, ser_threads, ser_lock):
        threading.Thread.__init__(self)
        self.conn = conn
        self.net_threads = net_threads
        self.ser_threads = ser_threads
        self.net_lock = net_lock
        self.ser_lock = ser_lock

    def run(self):
        print("Starting console thread {}\n".format(self.name))
        # Sending message to connected client
        # self.conn.send('Welcome to the server. Type "exit_term" to exit\r\n'.encode("ascii")) #send only takes string

        global exit_flag
        while not exit_flag:
            #Receiving from client
            try:            
                data = self.conn.recv(1024)
            except socket.error as e:
                print("Error initially receiving data, happens when remote forcibly exits")
                print("\t", e.__str__())
                break
            
            # When tera term first connects, it sends junk which can cause issues.
            if data == b'\xff\xfb\x18\xff\xfd\x03\xff\xfb\x03\xff\xfd\x01\xff\xfb\x1f' \
                or data == b'\xff\xf1' \
                or data == b'\x00':
                print("Tera Term on {} sent some gibborish, ignoring...".format(self.name))
                data = ""
            
            if data:
                print("{} sent '{}'".format(self.name, data.encode("string_escape")))

                # For closing the remote terminal.
                if "exit_term" in data.decode("ASCII", "ignore"):
                    break

                try:
                    # self.net_lock.acquire()
                    # for thread in self.net_threads:
                    #     # Cleanup the string going to the terminals
                    #     temp = ""
                    #     if b'\x00' in data:
                    #         temp = data.replace(b'\x00', b'\n')
                    #     # Send data to the terminals which aren't this one.
                    #     if self.name != thread.name:
                    #         thread.conn.sendall(data)
                    # self.net_lock.release()
                    self.ser_lock.acquire()
                    for thread in self.ser_threads:
                        # Cleanup the string going to the com port
                        temp = ""
                        if b'\n' in data:
                            temp = data.replace(b'\n', b'\x00')
                        thread.serial.write(data)
                    self.ser_lock.release()
                except socket.error as e:
                    print("Error sending data to socket")
                    print(e.__str__())
                    exit_flag = 1
                    break
                except serial.serialutil.SerialException as e:
                    print("Error sending data to serial port")
                    print(e.__str__())
                    exit_flag = 1
                    break
         
        #came out of loop. Close the thread and remove from list of threads.
        for number, thread in enumerate(self.net_threads):
            if thread.name == self.name:
                self.net_threads.pop(number)

        self.conn.close()
        print("Stopped console thread {}\n".format(self.name))

class serToNetThread(threading.Thread):
    def __init__(self, com_port, net_threads, net_lock, ser_threads, ser_lock, baudrate = 115200):
        threading.Thread.__init__(self)
        self.com_port = com_port
        self.net_threads = net_threads
        self.ser_threads = ser_threads
        self.net_lock = net_lock
        self.ser_lock = ser_lock
        self.serial_baudrate = baudrate
        self.serial_buffer = ""
        self.serial = serial.Serial()
        self.init_serial_connection(com_port, baudrate)
        

    def init_serial_connection(self, com_port, baudrate):
        self.serial.close()
        try:
            self.serial = serial.Serial(com_port, baudrate)
        except serial.serialutil.SerialException as e:
            print("Error connecting to {}: {}\n".format(com_port, e.__str__()))
            exit(1)

    def run(self):
        print("Starting serial listener {}\n".format(self.name))
        global exit_flag

        with open("serial_output", "w") as writefile:
            while not exit_flag:
                while self.serial.inWaiting() > 0:
                    self.serial_buffer += (self.serial.read(1)).decode("ASCII",'ignore')
                
                if self.serial_buffer:
                    # Flush the buffer otherwise it will stop sending data after a while.
                    self.serial.reset_input_buffer()
                    writefile.write(self.serial_buffer)
                    try:
                        self.net_lock.acquire()
                        for thread in self.net_threads:
                            thread.conn.sendall(self.serial_buffer.encode("ASCII"))
                        self.net_lock.release()
                    except socket.error as e:
                        print("Error, Got bad data from socket\n\t")
                        print(e.__str__())
                        # self.init_serial_connection(self.com_port, self.serial_baudrate)
                    self.serial_buffer = ""

        #came out of loop. Close the thread and remove from list of threads.
        for number, thread in enumerate(self.ser_threads):
            if thread.name == self.name:
                self.ser_threads.pop(number)

        print("Stopped serial listener {}\n".format(self.name))

class telnetEjectThread(threading.Thread):
    """
    Since we can't actually kill the entire script without reconncecting
    due to the s.accept() blocking call, let's connect to ourselves
    and basically self-destruct.
    """
    def __init__(self, port, net_threads, ser_threads):
        threading.Thread.__init__(self)
        self.port = port
        self.net_threads = net_threads
        self.ser_threads = ser_threads

    def run(self):
        print("Starting self-destruct thread {}".format(self.name))
        global exit_flag
        while True:
            sleep(5)
            if exit_flag:
                self.tn = telnetlib.Telnet(host = "127.0.0.1",
                    port = self.port,
                    timeout = 1)
                self.tn.close()
                break
            # If no net threads, trigger the exit thread
            if not self.net_threads and self.ser_threads:
                exit_flag = 1
        print("Stopping self-destruct thread {}".format(self.name))

def telnet_server(host="", telnet_port=22, com_port="COM2"):
    net_lock = threading.Lock()
    ser_lock = threading.Lock()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Open Sockets
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print('Socket created')

        #Bind socket to local host and port
        try:
            s.bind((host, telnet_port))
        except OSError as e:
            print('Bind failed. Error Code : {}'.format(e))
            sys.exit(1)

        print('Socket bind on port {} complete'.format(telnet_port))
     
        #Start listening on socket
        s.listen(10)
        print('Socket now listening')
        print('Waiting on first telnet connection to open {} serial port'.format(com_port))
        global net_threads
        net_threads = []
        ser_threads = []
        tel_threads = []
        global exit_flag

        first_connect = 1

        #now keep talking with the client
        while not exit_flag:
            #wait to accept a connection - blocking call
            conn, addr = s.accept()
            if exit_flag:
                conn.close()
                break
            print('Connected with {}: {}\n'.format(addr[0], addr[1]))
            if first_connect:
                # Telnet thread to help kick us out, only spawn on first connect
                telthread = telnetEjectThread(telnet_port, net_threads, ser_threads)
                telthread.start()
                tel_threads.append(telthread)
                # COM port thread, only spawn on first connect
                serthread = serToNetThread(com_port, net_threads, net_lock, ser_threads, ser_lock)
                serthread.start()
                ser_threads.append(serthread)

            netthread = netToSerThread(conn, net_threads, net_lock, ser_threads, ser_lock)
            netthread.start()
            
            net_threads.append(netthread)
            first_connect = 0

        print("Waiting for the threads to all exit...\n")
        for t in net_threads:
            t.join()
        for t in ser_threads:
            t.join()
        for t in tel_threads:
            t.join()

        print("Finished.")
    finally:
        s.close()

if __name__ == "__main__":
    print(sys.version)
    parser = argparse.ArgumentParser(description='COM port to multiple telnet replicator')
    parser.add_argument('telnet_port', metavar='telnet_port', type=int, help='Telnet Port Number')
    parser.add_argument('com_port', metavar='com_port', type=str, help='COM port, ex: COM2')
    args = parser.parse_args()
    # print(args.telnet_port, isinstance(args.telnet_port, int))
    # print(args.com_port)
    # exit(0)
    telnet_server(telnet_port=args.telnet_port, com_port=args.com_port)
    exit(0)
