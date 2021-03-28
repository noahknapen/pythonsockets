import socket
import threading
import datetime
import os
import re


class HttpServer:
    """
    A class where an object represents an HTTP server

    Attributes
    ----------
    HttpServer.PORT: int
        a static integer specifying the port to use for communication between server and clients
    HttpServer.HEADER: int
        a static integer specifying the maximum bytes to be received at once
    HttpServer.FORMAT: str
        a static string representing the format used to decode received data
    HttpServer.DISCONNECT_MESSAGE: str
        a static string representing the message the client has to send to disconnect from the server
    ipv4: str
        a string representing the IPv4 address of the server
    addr: tuple
        a tuple of length 2 with the first position being the IPv4 address and the second being the port

    """

    PORT: int = 5055
    HEADER: int = 1
    FORMAT: str = 'latin-1'
    REQUESTS = ["GET", "HEAD", "PUT", "POST"]
    DISCONNECT_MESSAGE: str = "DISCONNECT"
    INDEX_DATE_LAST_MOD: str = "18 Mar 2021 20:44:30 GMT"
    SEA_DATE_LAST_MOD: str = "18 Mar 2021 20:44:30 GMT"
    MONTHS: dict = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9,
                    "Oct": 10, "Nov": 11, "Dec": 12}

    ipv4: str
    addr: tuple
    server: socket.socket

    def __init__(self):
        print("[SETUP] server is starting...")
        # AF_INET says we work with IPv4 addresses
        # SOCK_STREAM says data will be streamed through the socket
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        """Bind the server to this machine's IPv4 address and start listening for connections.

        This is the only function that should be called.
        After connecting, a handler will be called to ask and handle http requests.
        """
        self.ipv4 = socket.gethostbyname(socket.gethostname())
        self.addr = (self.ipv4, HttpServer.PORT)
        self.server.bind(self.addr)
        print("[SETUP] server bound to IPv4 address", self.ipv4, "on port", HttpServer.PORT)
        self.server.listen()
        print("[SETUP] server listening for connections")

    def __manage_client_thread(self, conn_socket: socket.socket, address: tuple):
        """Manages a single client.

        Checks the received messages of the given client for HTTP commands and acts accordingly

        Parameters
        ----------
        conn_socket: socket.socket
            Socket to identify the client
        address: tuple
            Tuple consisting of length two with respectively the IPv4 address and port of the client
        """
        print("[THREAD] new thread started for client")
        connected = True

        while connected:
            request_header = HttpServer.get_request_header(conn_socket)
            split_request_header = request_header.split()
            file = split_request_header[1]
            print("[RECV] header received from IPv4 address", address[0], ":", request_header)

            if not HttpServer.is_valid_http_request(split_request_header):
                http_message = HttpServer.create_400_response()
                pass
            else:
                if file == "/":
                    file = "/index.html"

                put_or_post = HttpServer.is_put_or_post(split_request_header)
                try:
                    if put_or_post:
                        request_body = HttpServer.get_request_body(conn_socket, request_header)
                        status_code = HttpServer.get_status_code_for_put_or_post(request_header, file)

                        if status_code == 204:
                            if split_request_header[0] == "PUT":
                                f = open(file[1:], "w")
                            else:
                                f = open(file[1:], "a")

                            f.write(request_body)
                            f.close()
                            http_message = HttpServer.create_204_response()
                        elif status_code == 501:
                            http_message = HttpServer.create_501_response()
                        else:  # status code is 201
                            f = open(file[1:], "x")
                            f.write(request_body)
                            f.close()
                            http_message = self.create_201_response(file)

                    else:
                        if split_request_header[0] == "GET":
                            # GET needs filename
                            status_code = HttpServer.get_status_code_for_get(request_header, file)
                        else:
                            status_code = HttpServer.get_status_code_for_head(file)

                        if status_code == 404:
                            http_message = HttpServer.create_404_response()
                        elif status_code == 304:
                            http_message = HttpServer.create_304_response()
                        else:  # status code is 200
                            http_message = HttpServer.create_200_response(file)
                except Exception:
                    http_message = HttpServer.create_500_response()

            conn_socket.send(http_message)

            # determine if connection has to be closed
            conn_str = "Connection:"
            conn_begin_ind = request_header.find(conn_str)

            if conn_begin_ind != -1:
                conn_end_ind = request_header[conn_begin_ind:].find("\r\n") + conn_begin_ind
                conn_status = request_header[conn_begin_ind+len(conn_str):conn_end_ind].strip()
                if conn_status == "close":
                    conn_socket.close()
                    connected = False
                    print("[THREAD] client thread ended")

    def loop(self):
        """Loop to execute as long as server is online

        This function will manage connections
        If a client disconnects, the user will be asked if the server has to shut down or not.
        """
        disconnect = False

        while not disconnect:
            print("[CONNECTION] waiting for new connection")
            # To use accept(), server must be bound to an address and listening for connections
            # conn is a new socket object usable to send and receive data
            # addr is address bound to socket on other side of the connection
            conn, addr = self.server.accept()  # accept() is blocking method untill client connects
            print("[CONNECTION] new connection:", addr[0], "accepted.")
            client_thread = threading.Thread(target=self.__manage_client_thread, args=(conn, addr), daemon=True)
            client_thread.start()

    @staticmethod
    def date_older_than_file_date(date_and_time: str, file: str) -> bool:
        """Return whether the given date is older than the last modified date of the given file

        Parameters
        ----------
        date_and_time: str
            Pass data: <weekday>, <day of the month> <3 first letters of month> <year> <hours:minutes:seconds> GMT
            An example is: Thu, 18 Mar 2021 20:44:30 GMT

        file: str
            The file, starting with a "/", to get the last modified date of

        Returns
        -------
        bool
            True if given date is older than the last modified date of then given file, False otherwise
        """
        # compare_date: 0 is monthday, 1 is monthname, 2 is year, 3 is time, 4 is GMT
        if file[1:] == "index.html":
            compare_date = HttpServer.INDEX_DATE_LAST_MOD.split()
        else:
            compare_date = HttpServer.SEA_DATE_LAST_MOD.split()

        # 0 is weekday, 1 is monthday, 2 is monthname, 3 is year, 4 is time, 5 is GMT
        split_date_and_time = date_and_time.split()

        if split_date_and_time[3] == compare_date[2]:
            if HttpServer.MONTHS.get(split_date_and_time[2]) == HttpServer.MONTHS.get(compare_date[1]):
                if split_date_and_time[1] == compare_date[0]:
                    # 0 is hours, 1 is minutes, 2 is seconds
                    split_time = split_date_and_time[4].split(":")
                    split_compare_time = compare_date[3].split(":")

                    if split_time[0] == split_compare_time[0]:
                        if split_time[1] == split_compare_time[1]:
                            if split_time[2] == split_compare_time[2]:
                                return True
                            elif split_time[2] < split_compare_time[2]:
                                return True
                            else:
                                return False
                        elif split_time[1] < split_compare_time[1]:
                            return True
                        else:
                            return False
                    elif split_time[0] < split_compare_time[0]:
                        return True
                    else:
                        return False
                elif split_date_and_time[1] < compare_date[0]:
                    return True
                else:
                    return False
            elif HttpServer.MONTHS.get(split_date_and_time[2]) < HttpServer.MONTHS.get(compare_date[1]):
                return True
            else:
                return False
        elif split_date_and_time[3] < compare_date[2]:
            return True
        else:
            return False

    @staticmethod
    def get_request_header(conn_socket: socket.socket) -> str:
        """Get the header of the request of the client specified by the given socket

        Parameters
        ----------
        conn_socket: socket.socket
            Socket object to identify the client

        Returns
        -------
        str
            Returns the received header as a string
        """
        raw_double_new_line = "\r\n\r\n".encode(HttpServer.FORMAT)
        raw_request_header = conn_socket.recv(HttpServer.HEADER)

        while raw_double_new_line not in raw_request_header:
            raw_request_header += conn_socket.recv(HttpServer.HEADER)

        return raw_request_header.decode(HttpServer.FORMAT)

    @staticmethod
    def get_request_body(conn_socket: socket.socket, request_header: str) -> str:
        """Get the body of the request of the client specified by the given socket

        Only call this function if you are sure there is a body for the request

        Parameters
        ----------
        conn_socket: socket.socket
            Socket object to identify the client
        request_header: str
            The header of the request that has already been received from the client

        Returns
        -------
        str
            Returns the received body as a string
        """
        new_line = "\r\n"
        content_header = "Content-Length:"
        raw_body = b''
        begin_chunksize_ind = request_header.find(content_header) + len(content_header)
        end_chunksize_ind = request_header[begin_chunksize_ind:].find(new_line)
        chunk_size = int(request_header[begin_chunksize_ind:begin_chunksize_ind + end_chunksize_ind])

        while chunk_size != 0:
            raw_body += conn_socket.recv(HttpServer.HEADER)
            chunk_size -= 1

        return raw_body.decode(HttpServer.FORMAT)

    @staticmethod
    def is_valid_http_request(split_request_header: list) -> bool:
        """Given a request header split in separate words, determine whether it is a valid HTTP request

        To be a valid HTTP request, the request must:
            - begin with a supported HTTP command
            - must have a filename as the second word
            - must have HTTP/1.1 specified as the third word

        Parameters
        ----------
        split_request_header: list
            An HTTP request, split up in separate words

        Returns
        -------
        bool
            True if the conditions specified above are met, False otherwise
        """
        if len(split_request_header) < 3:
            return False
        if split_request_header[0] not in HttpServer.REQUESTS:
            return False
        if split_request_header[2] != "HTTP/1.1":
            return False
        if split_request_header[0] == "PUT" or split_request_header[0] == "POST":
            # see if there aren't any directories preceding the file
            occurrences = re.findall("/", split_request_header[1])
            if len(occurrences) > 1:
                return False

        return True

        # return len(split_request_header) < 3 or \
        #        split_request_header[0] not in HttpServer.REQUESTS or \
        #        split_request_header[2] != "HTTP/1.1"

    @staticmethod
    def is_put_or_post(split_request_header: list) -> bool:
        """Given a request header split in separate words, determine whether the HTTP command is PUT or POST

        Parameters
        ----------
        split_request_header: list
            An HTTP request, split up in separate words

        Returns
        -------
        bool
            True if the HTTP command is PUT or POST, False otherwise

        """
        if split_request_header[0] == "PUT":
            return True
        elif split_request_header[0] == "POST":
            return True

        return False

    @staticmethod
    def get_status_code_for_head(file: str) -> int:
        """Returns the status code if a HEAD request was received

        Parameters
        ----------
        file: str
            Filename, starting with a "/" to get the specified file

        Returns
        -------
        int
            Returns either the status code 200 or 404
        """
        if file == "/":
            file = "/index.html"

        if not os.path.isfile(file[1:]):
            return 404

        return 200

    @staticmethod
    def get_status_code_for_get(request_header: str, file: str) -> int:
        """Returns the status code if a GET request was received

        Parameters
        ----------
        request_header: str
            Request header of the GET request
        file: str
            Filename, starting with a "/" to get the specified file

        Returns
        -------
        int
            Returns either the status code 200, 304 or 404
        """
        modified = True
        modified_header = "If-Modified-Since:"
        if file == "/":
            file = "/index.html"

        if not os.path.isfile(file[1:]):
            return 404

        # check for If_Modified_Since
        begin_mod_date_ind = request_header.find(modified_header)

        if begin_mod_date_ind != -1:
            new_line = "\r\n"
            end_mod_date_ind = request_header[begin_mod_date_ind:].find(new_line) + begin_mod_date_ind
            date_and_time = request_header[begin_mod_date_ind:end_mod_date_ind][len(modified_header):]

            if not HttpServer.date_older_than_file_date(date_and_time, file):
                modified = False

        if modified is True:
            return 200
        else:
            return 304

    @staticmethod
    def get_status_code_for_put_or_post(request_header: str, file: str) -> int:
        """Returns the status code if a PUT or POST request was received

        Parameters
        ----------
        request_header: str
            Request header of the PUT or POST request
        file: str
            Filename, starting with a "/" to get the specified file

        Returns
        -------
        int
            Returns either the status code 200, 201 or 501
        """
        ctype = "Content-Type: text/html"
        if file == "/":
            file = "/index.html"

        if request_header.find(ctype) == -1:
            return 501

        if not os.path.isfile(file[1:]):
            return 201

        return 204

    @staticmethod
    def get_content_data(file: str) -> str:
        """Returns the Content-Length and Content-Type headers of the specified file

        Parameters
        ----------
        file: str
            File, starting with "/", to compute content data from

        Returns
        -------
        str
            Content-Length and Content-Type header, separated by CRLF
        """
        file = file[1:]
        file_extension = file.split(".")

        if file_extension[-1] == "jpg":
            content_type = "Content-Type: image/jpeg"
        elif file_extension[-1] == "png" or file_extension[-1] == "gif":
            content_type = "Content-Type: image/" + file_extension[-1]
        else:
            content_type = "Content-Type: text/" + file_extension[-1]

        content_length = "Content-Length: " + str(os.stat(file).st_size)

        return content_length + "\r\n" + content_type

    @staticmethod
    def create_body(file: str) -> bytes:
        """Returns the contents of the given files as bytes

        Parameters
        ----------
        file: str
            File, starting with "/", to gather content from

        Returns
        -------
        bytes
            Content of the file in bytes
        """
        f = open(file[1:], mode='rb')
        body = f.read()
        f.close()
        return body

    @staticmethod
    def create_200_response(file: str) -> bytes:
        """Returns the header and body for the 200 status code

        Parameters
        ----------
        file: str
            File, starting with "/" to gather data from to compute a correct header and body

        Returns
        -------
        bytes
            Returns the header and body for the 200 OK status code
        """
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        content_data = HttpServer.get_content_data(file)

        header = "HTTP/1.1 200 OK" + "\r\nDate: " + date + "\r\n" + content_data + "\r\n\r\n"
        print(header)
        raw_header = header.encode(HttpServer.FORMAT)
        raw_body = HttpServer.create_body(file)
        response = raw_header + raw_body

        return response

    def create_201_response(self, file: str) -> bytes:
        """Returns the header and body for the 201 status code

        Parameters
        ----------
        file: str
            File, starting with "/", to gather data from to compute a correct header and body

        Returns
        -------
        bytes
            Returns the header and body for the 201 Created status code
        """
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        location = "http://" + self.ipv4 + ":" + str(HttpServer.PORT) + file
        header = "HTTP/1.1 201 Created" + "\r\nDate: " + date + "\r\nLocation:" + location + "\r\n\r\n"

        print(header)
        return header.encode(HttpServer.FORMAT)

    @staticmethod
    def create_204_response() -> bytes:
        """Returns the header and body for the 204 status code

        Returns
        -------
        bytes
            Returns the header and body for the 204 No Content status code
        """
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        header = "HTTP/1.1 204 No Content" + "\r\nDate: " + date + "\r\n\r\n"

        print(header)
        return header.encode(HttpServer.FORMAT)

    @staticmethod
    def create_304_response() -> bytes:
        """Returns the header and body for the 304 status code

        Returns
        -------
        bytes
           Returns the header and body for the 304 Not Modified status code
        """
        content_data = HttpServer.get_content_data("/not_modified.html")
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        header = "HTTP/1.1 304 Not Modified" + "\r\nDate: " + date + "\r\n" + content_data + "\r\n\r\n"
        raw_header = header.encode(HttpServer.FORMAT)
        print(header)
        raw_body = HttpServer.create_body("/not_modified.html")
        response = raw_header + raw_body

        return response

    @staticmethod
    def create_400_response() -> bytes:
        """Returns the header and body for the 400 status code

        Returns
        -------
        bytes
            Returns the header and body for the 400 Bad Request status code
        """
        content_data = HttpServer.get_content_data("/bad_request.html")
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        header = "HTTP/1.1 400 Bad Request" + "\r\nDate: " + date + "\r\n" + content_data + "\r\n\r\n"
        raw_header = header.encode(HttpServer.FORMAT)
        print(header)
        raw_body = HttpServer.create_body("/bad_request.html")
        response = raw_header + raw_body

        return response

    @staticmethod
    def create_404_response() -> bytes:
        """Returns the header and body for the 404 status code

        Returns
        -------
        bytes
            Returns the header and body for the 404 Not Found status code
        """
        content_data = HttpServer.get_content_data("/not_found.html")
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        header = "HTTP/1.1 404 Not Found" + "\r\nDate: " + date + "\r\n" + content_data + "\r\n\r\n"
        raw_header = header.encode(HttpServer.FORMAT)
        print(header)
        raw_body = HttpServer.create_body("/not_found.html")
        response = raw_header + raw_body

        return response

    @staticmethod
    def create_500_response() -> bytes:
        """Returns the header and body for the 500 status code

        Returns
        -------
        bytes
           Returns the header and body for the 500 Internal Server Error status code
        """
        content_data = HttpServer.get_content_data("/internal_server_error.html")
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        header = "HTTP/1.1 500 Internal Server Error" + "\r\nDate: " + date + "\r\n" + content_data + "\r\n\r\n"
        raw_header = header.encode(HttpServer.FORMAT)
        print(header)
        raw_body = HttpServer.create_body("/internal_server_error.html")
        response = raw_header + raw_body

        return response

    @staticmethod
    def create_501_response() -> bytes:
        """Returns the header and body for the 501 status code

        Returns
        -------
        bytes
           Returns the header and body for the 501 Not Implemented status code
        """
        date = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        header = "HTTP/1.1 501 Not Implemented" + "\r\nDate: " + date + "\r\n\r\n"
        print(header)
        return header.encode(HttpServer.FORMAT)


if __name__ == "__main__":
    server = HttpServer()
    server.connect()
    server.loop()
