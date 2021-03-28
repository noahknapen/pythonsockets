import os
import socket
from bs4 import BeautifulSoup
import sys


class HttpClient:
    """A class where an object represents an HTTP client

    Attributes
    ----------
    HttpClient.FORMAT: str
        A static string representing the message the client has to send to disconnect from the server
    HttpClient.HEADER: int
        A static integer specifying the maximum bytes to be received at once
    HttpClient.HTTP_VERSION: str
        Specifies the HTTP version used in this client
    uri: str
        Hostname in Internet domain notation or IPv4 address of the server
    port: int
        An integer specifying the port to use for communication between client and server
    http_command: str
        The HTTP command to execute (supported commands are HEAD, GET, PUT, POST
    file_name: str
        The file to execute the HTTP command on
    client: socket.socket
        The socket object representing the client
    format_body: str
        Not implemented but should take over from FORMAT to get better decodings
    close_connection: bool
        Determine if connection has to be closed after sending a GET request
    """
    FORMAT: str = 'latin-1'  # alias for iso-8859-1 (default charset for HTTP)
    HEADER: int = 4096
    HTTP_VERSION: str = 'HTTP/1.1'
    FORMATS: dict = {"latin-1": ["iso-8859-1", "latin-1"], "utf-8": ["utf", "utf8", "utf-8"], }

    uri: str
    port: int
    http_command: str
    file_name: str
    client: socket.socket
    format_body: str
    close_connection: bool

    def __init__(self):
        print("[SETUP] client is starting...")
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.format_body = HttpClient.FORMAT
        self.close_connection = False

        try:
            self.http_command = sys.argv[1]
            self.uri, self.file_name = HttpClient.get_remote_uri_and_filename(sys.argv[2])
            self.port = int(sys.argv[3])
        except IndexError:
            print("[ERROR] pass arguments in following order: COMMAND, URI, PORT")
        else:
            self.main()

    @staticmethod
    def create_file_location(loc: str) -> str:
        """Creates a proper filename for the given location
        If the given location points to directories, the returned location will contain only the filename

        Parameters
        ----------
        loc: str
            The location pointing to the file

        Returns
        -------
        str
            Returns the filename, without parent directories but it starts with a "/"
        """
        slash = "/"
        reverse_data = loc[-4:]  # "/" will not be in the type of the file already in reverse_data
        reverse_data_ind = -4

        while slash not in reverse_data:
            reverse_data_ind -= 1
            reverse_data = loc[reverse_data_ind:]

        return reverse_data

    @staticmethod
    def get_remote_uri_and_filename(uri_to_filename: str) -> tuple:
        """Split the remote URI and filename

        Parameters
        ----------
        uri_to_filename: str
            The URI, appended with a filename to look for

        Returns
        -------
        tuple
            Returns respectively the uri and filename
        """
        wrld_wide_web = "www"
        slashstr = "/"

        begin_uri_ind = uri_to_filename.find(wrld_wide_web)
        end_uri_ind = uri_to_filename[begin_uri_ind:].find(slashstr) + begin_uri_ind

        if begin_uri_ind == -1:
            end_uri_ind = uri_to_filename.find(slashstr)
            if end_uri_ind == -1:
                uri = uri_to_filename
                file = "/"
            else:
                uri = uri_to_filename[:end_uri_ind]
                file = uri_to_filename[end_uri_ind:]
        elif end_uri_ind == begin_uri_ind - 1:
            uri = uri_to_filename
            file = "/"
        else:
            uri = uri_to_filename[begin_uri_ind: end_uri_ind]
            file = uri_to_filename[end_uri_ind:]

        return uri, file

    def main(self):
        """Connect the socket to the given URI via the given port and handle the HTTP request

        """
        addr = (self.uri, self.port)
        try:
            self.client.connect(addr)
        except socket.gaierror:
            print("[ERROR] not a valid URI. Try again please...")
        else:
            print("[SETUP] client connected to IPv4 address", self.uri, "on port", self.port)
            self.handler()

    def handler(self):
        """Handle the request from beginning to end

        Supported HTTP commands are HEAD, GET, PUT and POST
        """
        msg = self.create_http_request()
        self.send(msg)

        if self.file_name == "/":
            self.file_name = "/index.html"
        else:
            self.file_name = HttpClient.create_file_location(self.file_name)

        if self.http_command == "HEAD":
            recv_raw, _ = self.recv_header()
            recv = recv_raw.decode(self.format_body)
            recv_with_updated_imgs = self.update_images(recv)
            self.write_to_html_file(recv_with_updated_imgs)
        elif self.http_command == "PUT":
            recv_raw = self.recv_all_data()
            if recv_raw != b'':
                recv = recv_raw.decode(self.format_body)
                recv_with_updated_imgs = self.update_images(recv)
                self.write_to_html_file(recv_with_updated_imgs)
        elif self.http_command == "POST":
            recv_raw = self.recv_all_data()
            if recv_raw != b'':
                recv = recv_raw.decode(self.format_body)
                recv_with_updated_imgs = self.update_images(recv)
                self.write_to_html_file(recv_with_updated_imgs)
        else:   # http_command == "GET" or it is a bad request
            recv_raw = self.recv_all_data()
            recv = recv_raw.decode(self.format_body)
            recv_with_updated_imgs = self.update_images(recv)
            self.write_to_html_file(recv_with_updated_imgs)

        self.disconnect()
        print("[CONNECTION] Client terminated")

    def create_http_request(self) -> str:
        """Create a valid HTTP request

        The supported HTTP version is 1.1

        Returns
        -------
        str
            Returns a valid HTTP request to send to a server
        """

        if self.http_command == "PUT" or self.http_command == "POST":
            ctype = "text/html"
            body = input("Enter data to insert: ")
            clength = len(body.encode(HttpClient.FORMAT))
            msg = self.http_command + " " + self.file_name + " HTTP/1.1\r\nHost: " + str(self.uri) \
                + "\r\nConnection: close" \
                + "\r\nContent-Type: " + ctype \
                + "\r\nContent-Length: " + str(clength) + "\r\n\r\n" + body + "\r\n"
        else:
            msg = self.http_command + " " + self.file_name + " HTTP/1.1\r\nHost: " + str(self.uri) \
                + "\r\n\r\n"

        return msg

    def create_secondary_http_command(self, img_loc: str) -> str:
        """
        Given the location of a file, create a valid HTTP GET command

        Parameters
        ----------
        img_loc: str
            The remote location of the image

        Returns
        -------
        str
            Valid HTTP request
        """
        if self.close_connection is False:
            msg = "GET " + img_loc + " HTTP/1.1\r\nHost: " + str(self.uri) + "\r\n\r\n"
        else:
            msg = "GET " + img_loc + " HTTP/1.1\r\nHost: " + str(self.uri) \
                  + "\r\nConnection: close"\
                  + "\r\n\r\n"
        return msg

    def send(self, msg: str):
        """Sends a message to the server

        Parameters
        ----------
        msg: str
            Specifies the message to send to the server
        """
        message = msg.encode(HttpClient.FORMAT)
        self.client.send(message)
        print("[MESSAGE] message sent:", msg)

    def recv_header(self) -> tuple:
        """Receive header from the server

        Since bytes get received in chunks from the server, a part of the body can be fetched while retrieving
        the header if the HTTP command is a GET.

       Returns
       -------
       tuple
           Returns the data gotten from the server in bytes in a tuple with the header and
           the beginning part of the body, respectively
       """
        print("[RECV] receiving header data...")
        raw_data = b''
        double_new_line = "\r\n\r\n"
        raw_double_new_line = double_new_line.encode(HttpClient.FORMAT)
        end_header_ind = raw_data.find(raw_double_new_line)

        while end_header_ind == -1:
            raw_data += self.client.recv(HttpClient.HEADER)
            end_header_ind = raw_data.find(raw_double_new_line)

        raw_header = raw_data[:end_header_ind]
        raw_body = raw_data[end_header_ind + 4:]
        return raw_header, raw_body

    def recv_all_data(self) -> bytes:
        """Receive data from the server in response to a HTTP GET command

        Supported headers are: 'Content-Length' and 'Transfer-Encoding: chunked'

        Returns
        -------
        bytes
            Returns the data gotten from the server in bytes
        """
        raw_header, raw_begin_of_body = self.recv_header()
        print(raw_header.decode(HttpClient.FORMAT))
        print("[RECV] receiving body data...")
        raw_content_header = "Content-Length:".encode(HttpClient.FORMAT)
        raw_transfer_header = "Transfer-Encoding".encode(HttpClient.FORMAT)
        raw_charset_header = "charset=".encode(HttpClient.FORMAT)
        raw_new_line = "\r\n".encode(HttpClient.FORMAT)

        begin_charset_ind = raw_header.find(raw_charset_header) + len(raw_charset_header)

        if begin_charset_ind == len(raw_charset_header) - 1:
            pass
        else:
            end_charset_ind = raw_header[begin_charset_ind:].find(raw_new_line) + begin_charset_ind
            raw_charset = raw_header[begin_charset_ind:end_charset_ind]
            charset = raw_charset.decode(HttpClient.FORMAT).strip().lower()

            for key in HttpClient.FORMATS.keys():
                for value in HttpClient.FORMATS.get(key):
                    if value == charset:
                        self.format_body = key

        begin_chunksize_ind = raw_header.find(raw_content_header) + len(raw_content_header)

        if begin_chunksize_ind != len(raw_content_header) - 1:
            # content-length header
            end_chunksize_ind = raw_header[begin_chunksize_ind:].find(raw_new_line) + begin_chunksize_ind

            if end_chunksize_ind == begin_chunksize_ind - 1:
                chunk_size = int(raw_header[begin_chunksize_ind:]) - len(raw_begin_of_body)
            else:
                chunk_size = int(raw_header[begin_chunksize_ind:end_chunksize_ind]) - len(raw_begin_of_body)

            raw_body = raw_begin_of_body + self.__recv_content_length(chunk_size)

            return raw_body
        elif raw_header.find(raw_transfer_header) != -1:
            # transfer-encoding header
            end_chunksize_ind = raw_begin_of_body.find(raw_new_line)

            while end_chunksize_ind == -1:
                raw_begin_of_body += self.client.recv(HttpClient.HEADER)
                end_chunksize_ind = raw_begin_of_body.find(raw_new_line)

            # remove chunksize from body
            raw_begin_of_body_wo_chunk = raw_begin_of_body[end_chunksize_ind+len(raw_new_line):]
            chunk_size = int(raw_begin_of_body[:end_chunksize_ind], 16) - len(raw_begin_of_body_wo_chunk)
            raw_body = self.__recv_transfer_encoding_chunked(chunk_size, raw_begin_of_body_wo_chunk)

            return raw_body
        else:
            return b''

    def __recv_content_length(self, chunk_size: int) -> bytes:
        """Gives the html body when the page uses 'Content-Length: '

        Parameters
        ----------
        chunk_size: int
            Specifies the size of one chunk and therefore of all future chunks

        Returns
        -------
        bytes
            Returns the body in bytes
        """
        raw_data = b''

        while len(raw_data) < chunk_size:
            if chunk_size - len(raw_data) < HttpClient.HEADER:
                raw_data += self.client.recv(chunk_size - len(raw_data))
            else:
                raw_data += self.client.recv(HttpClient.HEADER)

        return raw_data

    def __recv_transfer_encoding_chunked(self, chunk_size: int, body: bytes = b'') -> bytes:
        """Gives the html body when the page uses 'Transfer-Encoding: chunked'

        Parameters
        ----------
        chunk_size: int
            Specifies the size of the next chunk to receive

        body: bytes
            Holds the body of the already received chunks.
            Its default value is None

        Returns
        -------
        bytes
            Returns the body in bytes
        """
        if chunk_size == 0:
            return body

        raw_data = b''

        while len(raw_data) < chunk_size:
            if chunk_size - len(raw_data) < HttpClient.HEADER:
                raw_data += self.client.recv(chunk_size - len(raw_data))
            else:
                raw_data += self.client.recv(HttpClient.HEADER)

        # receive CRLF, which is irrelevant
        _ = self.client.recv(1)
        _ = self.client.recv(1)

        raw_new_chunk_size = self.client.recv(1)
        new_line = "\r\n"
        raw_new_line = new_line.encode(HttpClient.FORMAT)

        while raw_new_line not in raw_new_chunk_size:
            raw_new_chunk_size += self.client.recv(1)

        raw_new_chunk_size = raw_new_chunk_size[:-2]
        new_chunk_size = int(raw_new_chunk_size.decode(HttpClient.FORMAT), 16)

        if body == b'':
            body = raw_data
        else:
            body += raw_data

        return self.__recv_transfer_encoding_chunked(new_chunk_size, body)

    def retrieve_secondary_file(self, src: str) -> tuple:
        """Retrieve an embedded file

        This is a helpfunction for update_images(data)

        Parameters
        ----------
        src: str
            The location where to find the file

        Returns
        -------
        tuple
            Tuple with the location where retrieved file is stored and the file in bytes, respectively
        """
        if src.find("http://") != -1:
            # location is on other server
            uri, file = HttpClient.get_remote_uri_and_filename(src)
            print("[CONNECTION] starting new client to retrieve an image")
            new_client = HttpClient()
            new_client.main()

            http_command = new_client.create_secondary_http_command(file)
            loc = HttpClient.create_file_location(file)
            new_client.send(http_command)
            recv_raw = new_client.recv_all_data()
            new_client.disconnect()
        else:
            # location is on same server

            http_command = self.create_secondary_http_command(src)
            loc = HttpClient.create_file_location(src)
            self.send(http_command)
            recv_raw = self.recv_all_data()

        return loc, recv_raw

    def update_images(self, data: str) -> str:
        """Search the given data for image references to get from the server and update file locations in the data

        This function searches image references, creates image HTTP commands and sends and receives them as well
        as write the gotten images to .png files and update their locations in the given data string.

        Parameters
        ----------
        data: str
            A .html file to search for images
        """
        soup = BeautifulSoup(data, 'html.parser')
        images = soup.find_all('img')
        added_slash = False
        # print(images)

        for img in images:
            img_src = [img['src']]

            try:
                img_lowsrc = img['lowsrc']
            except KeyError:
                pass
            else:
                img_src.append(img_lowsrc)

            for src in img_src:
                if src == img_src[-1]:
                    self.close_connection = True

                if src.find("http://") == -1 and src[0] != "/":
                    added_slash = True
                    src = "/" + src

                loc, recv_raw = self.retrieve_secondary_file(src)

                # write image to local file
                self.write_to_binary_file(loc, recv_raw)

                # replace location reference in data
                if added_slash is True:
                    src = src[1:]
                data = data.replace(src, loc[1:])  # do not add the slash of loc in the html file
                print("[WRITE] replace remote img loc:", src, "with local loc:", loc)

        return data

    def write_to_html_file(self, data: str):
        """Write given data to the file specified by the user

        Parameters
        ----------
        data: str
            The data to write to the recv.html file
        """
        try:
            os.mkdir("../" + self.uri)
        except FileExistsError:
            pass

        f = open("../" + self.uri + self.file_name, "w")
        f.write(data)
        print("[WRITE] written to .html file")
        f.close()

    def write_to_binary_file(self, loc: str, data: bytes):
        """Write the given data in bytes to the file specified by the given location

        Parameters
        ----------
        loc: str
            The filename, starting with "/", to store the .png file in
        data: bytes
            The data representing the PNG image
        """
        try:
            os.mkdir("../" + self.uri)
        except FileExistsError:
            pass

        f = open("../" + self.uri + loc, "wb")
        f.write(data)
        print("[WRITE] written to binary file loc")
        f.close()

    def disconnect(self):
        self.client.send("DISCONNECT".encode(HttpClient.FORMAT))
        self.client.close()


if __name__ == "__main__":
    client = HttpClient()
