import os,\
        sys,\
        time,\
        socket,\
        random,\
        paramiko,\
        netifaces,\
        threading,\
        traceback,\
        socketserver,\
        multiprocessing
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler #, TLS_FTPHandler ##Apparently the TLS module doesn't exist in Python3
from pyftpdlib.servers import ThreadedFTPServer
from paramiko import ServerInterface,\
                        AUTH_FAILED,\
                        AUTH_SUCCESSFUL,\
                        OPEN_SUCCEEDED
from sftpserver.stub_sftp import StubSFTPServer
from fbtftp.base_handler import BaseHandler,\
                                ResponseData
from fbtftp.base_server import BaseServer

####
import asyncio
from py3tftp.protocols import TFTPServerProtocol


####
from ptftplib.tftpserver import TFTPServer,\
                                TFTPServerHandler,\
                                TFTPServerGarbageCollector



########################
# Random Password Generator
# Returns 14 character string
#
def _random_string(num=14):
    Random_Str = ''
    char = 'abcdefghijklmnopqrstuvwxyz'
    CHAR = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    NUM = '1234567890'
    while len(Random_Str) < num:
        Random_Str += random.choice(char)
        Random_Str += random.choice(NUM)
        Random_Str += random.choice(CHAR)
    return Random_Str



########################
# Random RSA Key Generator
# Returns dictionary with
# private and public filenames
#
def _random_rsa():
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    priv = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    PRIV = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
    f = open(PRIV, "wb")
    f.write(priv)
    f.close()
    pub = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    PUB = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
    f = open(PUB, "wb")
    f.write(pub)
    f.close()
    return {'priv':PRIV,'pub':PUB}



from datetime import datetime, timedelta
import ipaddress

########################
# Random X509 Certificate Generator
# Returns dictionary with
#   private and public filenames
# Generates self signed certificate
#   for a hostname, and optional IP addresses.
#
def _selfsign_x509(hostname, ip_addresses=None, key=None):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    # Generate RSA key
    if key is None:
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname)
    ])

    alt_names = [x509.DNSName(hostname)]

    # allow addressing by IP, for when you don't have real DNS (common in most testing scenarios
    if ip_addresses:
        for addr in ip_addresses:
            # openssl wants DNSnames for ips...
            alt_names.append(x509.DNSName(addr))
            # ... whereas golang's crypto/tls is stricter, and needs IPAddresses
            # note: older versions of cryptography do not understand ip_address objects
            alt_names.append(x509.IPAddress(ipaddress.ip_address(addr)))

    san = x509.SubjectAlternativeName(alt_names)

    # path_len=0 means this cert can only sign itself, not other certs.
    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)
    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=10*365))
        .add_extension(basic_contraints, False)
        .add_extension(san, False)
        .sign(key, hashes.SHA256(), default_backend())
    )
    pub = cert.public_bytes(encoding=serialization.Encoding.PEM)
    PUB = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
    f = open(PUB, "wb")
    f.write(pub)
    f.close()

    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    PRIV = ''.join(i for i in [chr(random.randint(97,122)) for i in range(6)])
    f = open(PRIV, "wb")
    f.write(priv)
    f.close()


    return {'priv':PRIV,'pub':PUB}



########################
# Get Local IP
# Returns IP Address as String
#
#
def _get_local_ip():
    try:
        TEST = socket.socket()
        TEST.connect(('google.com', 443))
        Addr = TEST.getsockname()[0]
        TEST.close()
        return Addr
    except:
        print(traceback.format_exc())

########################
# Get Local INT
# Returns interface name as String
#
#
def _get_local_int():
    INTS = {}
    for Int in netifaces.interfaces():
      try:
        netifaces.ifaddresses(Int)[netifaces.AF_INET]
        INTS.update({f'{Int}': netifaces.ifaddresses(Int)[netifaces.AF_INET][0]['addr']})
      except:
        None
    Addr = _get_local_ip()
    for Int,addr in INTS.items():
        if addr == Addr:
            return Int




########################
# FTP Server Class
# Dir = str()
#   Ex: '/tmp'
# Port = int()
#   Ex: 2121
#
class ftp_server(object):
    # Create Random Username and Password
    def __init__(self,Dir=os.getcwd(),Port=2121):
        self.Dir = Dir
        self.Port = Port
        # Get Local Server Address and Interface Name
        self.Addr = _get_local_ip()
        self.Iface = _get_local_int()


    def _run_server(self):
        # Create Dummy Authorizer, with the random user/pass
        self.authorizer = DummyAuthorizer()
        self.authorizer.add_user(self.User, self.Pass, self.Dir, perm='elradfmw')
        self.handler = FTPHandler
        self.handler.authorizer = self.authorizer
        # Instantiate the FTP Server
        self.SRV = ThreadedFTPServer(('0.0.0.0',self.Port), self.handler)
        self.SRV.serve_forever()

    def start(self):
        # Random user/pass
        self.User = _random_string()
        self.Pass = _random_string()
        # Start separate process calling Run Server function
        self.srv = multiprocessing.Process(target=self._run_server)
        self.srv.start()

    def stop(self):
        # Close all connections immediately
        self.srv.kill()


########################
# SFTP Server Class
# Dir = str()
#   Ex: '/tmp'
# Port = int()
#   Ex: 22
# level = str()
#   Ex: 'DEBUG'
#
class sftp_server(object):
    def __init__(self,Dir=os.getcwd(),Port=22,level='INFO'):
        self.Dir = Dir
        self.Port = Port
        self.level = level
        # Get Local Server Address and Interface Name
        self.Addr = _get_local_ip()
        self.Iface = _get_local_int()

    class _stub_server(ServerInterface):
        # SubClass of Paramiko ServerInterface
        # Allowing authentication only for random user/pass
        def __init__(self,User,Pass):
            self.User = User
            self.Pass = Pass

        def check_auth_password(self, username, password):
            # Only randomly generated user/pass is allowed
            if (username == self.User) and (password == self.Pass):
                return AUTH_SUCCESSFUL
            else:
                return AUTH_FAILED

        def check_channel_request(self, kind, chanid):
            return OPEN_SUCCEEDED

        def get_allowed_auths(self, username):
            # List availble auth mechanisms
            return 'password'

    class _conn_handler_thd(threading.Thread):
        # Custom Connection Handler Thread for running server
        def __init__(self, conn, SRV, User, Pass, Dir, keyfile):
            threading.Thread.__init__(self)
            self.User = User
            self.Pass = Pass
            self.Dir = Dir
            self.SRV = SRV
            self._conn = conn
            self._keyfile = keyfile

        def run(self):
            self._host_key = paramiko.RSAKey.from_private_key_file(self._keyfile)
            self.transport = paramiko.Transport(self._conn)
            self.transport.add_server_key(self._host_key)

            self.STUB = StubSFTPServer
            self.STUB.ROOT = self.Dir

            self.transport.set_subsystem_handler(
                'sftp', paramiko.SFTPServer, StubSFTPServer)

            self.transport.start_server(server=self.SRV)
            self.channel = self.transport.accept()
            while self.transport.is_active():
                time.sleep(1)

    def _run_server(self):
        # Run Server function that calls Custom Connection Handler Thread
        paramiko_level = getattr(paramiko.common, self.level)
        paramiko.common.logging.basicConfig(level=paramiko_level)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.server_socket.bind(('0.0.0.0', self.Port))
        self.server_socket.listen(10)
        self.SRV = self._stub_server(self.User,self.Pass)
        while True:
            self._conn, self.addr = self.server_socket.accept()
            self.srvA = self._conn_handler_thd(self._conn, self.SRV, self.User, self.Pass, self.Dir, self._keyfile)
            self.srvA.deamon = True
            self.srvA.start()

    def start(self):
        # Random user/pass
        self.User = _random_string()
        self.Pass = _random_string()
        # Random RSA key pair
        self._keys = _random_rsa()
        self._keyfile = self._keys['priv']

        # Start separate process calling Run Server function
        self.srv = multiprocessing.Process(target=self._run_server)
        self.srv.start()

    def stop(self):
        # Close server socket immediately
        # This will print a Threading Exception to STDOUT, but will not throw a true exception
        self.srv.kill()
        os.remove(self._keys['priv'])
        os.remove(self._keys['pub'])




#########################
## Random PKI Generator
## Returns dictionary with
## private and public filenames
##
#def random_pki():
#    return {'priv':PRIV,'pub':PUB}
#
#########################
## TLS FTP Server Class
## FTPS... NOT SFTP
## Dir = str()
##   Ex: '/tmp'
## Port = int()
##   Ex: 2121
## cert = str()
## key = str()
#class ftps_server(object):
#    # Create Random Username and Password
#    def __init__(self,Dir='/tmp',Port=2121,cert='cert.pem',key=None):
#        self.Dir = Dir
#        self.Port = Port
#        self.cert = cert
#        self.key = key
#        self.User = Random_String()
#        self.Pass = Random_String()
#        self.authorizer = DummyAuthorizer()
#        self.authorizer.add_User(self.User, self.Pass, self.Dir, perm='elradfmw')
#        self.handler = TLS_FTPHandler
#        self.handler.certfile = self.cert
#        self.handler.keyfile = self.key
#        self.handler.authorizer = self.authorizer
#
#        self.SRV = ThreadedFTPServer(('0.0.0.0',self.Port), self.handler)
#
#    def _run_server(self):
#        self.SRV.serve_forever()
#
#    def start(self):
#        self.srv = threading.Thread(target=self._run_server)
#        self.srv.deamon = True
#        self.srv.start()
#
#    def stop(self):
#        self.SRV.close_all()
#

########################
# TFTP Server Sub-Class
#
class _tftp_ServerB:
    def __init__(self, Dir, Port):
        self.Dir = Dir
        self.Port = Port
        self.Addr = _get_local_ip()
        self.loop = asyncio.get_event_loop()
        self.srvA = self.loop.create_datagram_endpoint(
            lambda: TFTPServerProtocol(self.Addr, self.loop, None),
            local_addr=(self.Addr, self.Port,))
        self.transport, self.protocol = self.loop.run_until_complete(self.srvA)
    def serve_forever(self):
        self.loop.run_forever()

########################
# TFTP Server Class
# Dir = str()
#   Ex: '/tmp'
# Port = int()
#   Ex: 69
#
class tftp_serverB(object):
    # Create Random Username and Password
    def __init__(self,Dir='/tmp',Port=6969):
        self.Dir = Dir
        self.Port = Port
        # Get Local Server Address and Interface
        self.Addr = _get_local_ip()
        self.Iface = _get_local_int()

    def _run_server(self):
        self.SRV = _tftp_ServerB(self.Dir, self.Port)
        self.SRV.serve_forever()

    def start(self):
        # Start separate process calling Run Server function
        self.srv = multiprocessing.Process(target=self._run_server)
        self.srv.start()

    def stop(self):
        # Close all connections immediately
        self.srv.kill()


########################
# TFTP Server Sub-Class based on ptftplib
#
class _tftp_Server(TFTPServer):
    def __init__(self, iface, root, port,
                 strict_rfc1350=False, notification_callbacks=None):
        TFTPServer.__init__(self,iface,root,port)


        if notification_callbacks is None:
            notification_callbacks = {}
        self.root, self.port, self.strict_rfc1350 = \
            root, port, strict_rfc1350
        self.client_registry = {}

        # Get Local Server Address
        self.ip = _get_local_ip()
        self.server = socketserver.UDPServer((self.ip, port),
                                             TFTPServerHandler)
        self.server.root = self.root
        self.server.strict_rfc1350 = self.strict_rfc1350
        self.server.clients = self.client_registry
        self.cleanup_thread = TFTPServerGarbageCollector(self.client_registry)

        # Add callback notifications
        notify.CallbackEngine.install(l, notification_callbacks)

    def serve_forever(self):
        self.cleanup_thread.start()
        self.server.serve_forever()

########################
# TFTP Server Class
# Dir = str()
#   Ex: '/tmp'
# Port = int()
#   Ex: 69
#
class tftp_server(object):
    # Create Random Username and Password
    def __init__(self,Dir='/tmp',Port=6969):
        self.Dir = Dir
        self.Port = Port
        # Get Local Server Address and Interface
        self.Addr = _get_local_ip()
        self.Iface = _get_local_int()

    def _run_server(self):
        self.SRV = TFTPServer(self.Iface, self.Dir, port=self.Port)
        self.SRV.serve_forever()

    def start(self):
        # Start separate process calling Run Server function
        self.srv = multiprocessing.Process(target=self._run_server)
        self.srv.start()

    def stop(self):
        # Close all connections immediately
        self.srv.kill()




########################
# FBTFTP Server Class Only Compatible with Linux
# Dir = str()
#   Ex: '/tmp'
# Port = int()
#   Ex: 69
#
class fb_tftp_server(object):
    def __init__(self,Dir='/tmp',Port=6969):
        self.Dir = Dir
        self.Port = Port
        self.Addr = _get_local_ip()
        self.Iface = _get_local_int()
    def _run_server(self):
        self.SRV = _tftp_StaticServer(self.Addr, self.Port, retries=3, timeout=5,
                                    root=self.Dir, handler_stats_callback=None,
                                    server_stats_callback=None)
        self.SRV.run()
        self.SRV.serve_forever()
    def start(self):
        self.srv = multiprocessing.Process(target=self._run_server)
        self.srv.start()
    def stop(self):
        self.srv.kill()


class _tftp_FileResponseData(ResponseData):
    def __init__(self, path):
        self._size = os.stat(path).st_size
        self._reader = open(path, 'rb')
    def read(self, n):
        return self._reader.read(n)
    def size(self):
        return self._size
    def close(self):
        self._reader.close()


class _tftp_StaticHandler(BaseHandler):
    def __init__(self, server_addr, peer, path, options, root, stats_callback):
        self._root = root
        BaseHandler.__init__(self,server_addr, peer, path, options, stats_callback)
    def get_response_data(self):
        return _tftp_FileResponseData(os.path.join(self._root, self._path))


class _tftp_StaticServer(BaseServer):
    def __init__(self, address, port, retries, timeout, root,
                 handler_stats_callback, server_stats_callback=None):
        self._root = root
        self._handler_stats_callback = handler_stats_callback
        BaseServer.__init__(self,address, port, retries, timeout, server_stats_callback)
    def get_handler(self, server_addr, peer, path, options):
        return _tftp_StaticHandler(
            server_addr, peer, path, options, self._root,
            self._handler_stats_callback)


#from fbtftp.base_handler import BaseHandler
#from fbtftp.base_handler import ResponseData
#from fbtftp.base_server import BaseServer
#
#import os
#
#class FileResponseData(ResponseData):
#    def __init__(self, path):
#        self._size = os.stat(path).st_size
#        self._reader = open(path, 'rb')
#
#    def read(self, n):
#        return self._reader.read(n)
#
#    def size(self):
#        return self._size
#
#    def close(self):
#        self._reader.close()
#
#def print_session_stats(stats):
#    print(stats)
#
#def print_server_stats(stats):
#    counters = stats.get_and_reset_all_counters()
#    print('Server stats - every {} seconds'.format(stats.interval))
#    print(counters)
#
#class StaticHandler(BaseHandler):
#    def __init__(self, server_addr, peer, path, options, root, stats_callback):
#        self._root = root
#        super().__init__(server_addr, peer, path, options, stats_callback)
#
#    def get_response_data(self):
#        return FileResponseData(os.path.join(self._root, self._path))
#
#class StaticServer(BaseServer):
#    def __init__(self, address, port, retries, timeout, root,
#                 handler_stats_callback, server_stats_callback=None):
#        self._root = root
#        self._handler_stats_callback = handler_stats_callback
#        super().__init__(address, port, retries, timeout, server_stats_callback)
#
#    def get_handler(self, server_addr, peer, path, options):
#        return StaticHandler(
#            server_addr, peer, path, options, self._root,
#            self._handler_stats_callback)
#
#def main():
#    server = StaticServer(address='10.81.127.231', port=1069, retries=3, timeout=5,
#                          root=os.getcwd(),
#                          handler_stats_callback=print_session_stats,
#                          server_stats_callback=print_server_stats)
#    try:
#        server.run()
#    except KeyboardInterrupt:
#        server.close()
#
#if __name__ == '__main__':
#    main()



