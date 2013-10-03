from imbox.imap import ImapTransport
from imbox.parser import parse_folders
from imbox.parser import parse_email
from imbox.query import build_search_query
import re, imaplib
from imbox.parser import encode_utf7

class Imbox(object):

    def __init__(self, hostname, username=None, password=None, ssl=True):

        self.server = ImapTransport(hostname, ssl=ssl)
        self.connection = self.server.connect(username, password)
        self.username = username
        self.password = password


    def __enter__(self):
        self.connection()

    def __exit__(self, type, value, traceback):
        self.logout()

    def logout(self):
        self.connection.logout()

    def select_folder(self, name, **kwargs):
        folder = encode_utf7(name)
        read_only = kwargs.get('readonly', True)
        print folder, read_only
        self.connection.select(folder, readonly=read_only)

    def query_uids(self, **kwargs):
        query = build_search_query(**kwargs)

        message, data = self.connection.uid('search', None, query)
        return data[0].split()

    def fetch_by_uid(self, uid, **kwargs):
        folder = kwargs.get('folder', None)
        if folder:
            self.select_folder(folder)

        message, data = self.connection.uid('fetch', uid, '(X-GM-MSGID X-GM-THRID UID FLAGS BODY.PEEK[])') # Don't mark the messages as read, save bandwidth with PEEK
        raw_email = data[0][1]

        pattern = re.compile("^(\d+) \(X-GM-THRID (?P<gthrid>\d+) X-GM-MSGID (?P<gmsgid>\d+) UID (?P<uid>\d+) FLAGS \((?P<flags>[^\)]*)\)")
        self.maildata = {}
        headers = data[0][0]
        groups = pattern.match(headers).groups()
        self.maildata['GTHRID'] = groups[1]
        self.maildata['GMSGID'] = groups[2]
        self.maildata['UID'] = groups[3]
        self.maildata['FLAGS'] = groups[4]
        self.maildata['data'] = raw_email

        email_object = parse_email(self.maildata)
        return email_object

    def fetch_list(self, **kwargs):
        print kwargs
        uid_list = self.query_uids(**kwargs)

        for uid in uid_list:
            yield (uid, self.fetch_by_uid(uid))

    def mark_seen(self, uid):
        self.connection.uid('STORE', uid, '+FLAGS', '\\Seen')

    def delete(self, uid):
        mov, data = self.connection.uid('STORE', uid, '+FLAGS', '(\\Deleted)')
        self.connection.expunge()

    def copy(self, uid, destination_folder):
        return self.connection.uid('COPY', uid, destination_folder)

    def move(self, uid, destination_folder):
        if self.copy(uid, destination_folder):
            self.delete(uid)

    def messages(self, *args, **kwargs):
        folder = kwargs.get('folder', False)
        read_only = kwargs.get('readonly', True)
        
        if folder:
            self.select_folder(folder, readonly=read_only)

        return self.fetch_list(**kwargs)

    @property
    def folders(self):
        response = self.connection.list()
        status, folders = response[0], response[1]
        folders = parse_folders(folders)
        folder_list = []
        for box in folders:
            if( box != '"[Gmail]"'):  #ignore global [Gmail] mailbox
                 folder_list.append(box)
        print folder_list
        return folder_list
