# python_com_replicator
Python-based COM port to TCP replicator. This allows multiple users to talk to one common COM port through telnet. Only tested on Windows, should work with python 2.7 and 3.x

Requires pyserial

To Use:
* open command line
* pip install pyserial
* com_to_tcp_replicator.py <telnet_port (usually 22)> <com port>
>	    ex: com_to_tcp_replicator.py 22 COM2

* once running, find ip address/name of the computer you're on
* use a telnet client to telnet into the ip address/name found in the previous step