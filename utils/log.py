# -*- coding: utf-8 -*-
"""
Created on Wednesday, December 18, 17:15:27 GMT+5, 2019.

@author: Camilo Martínez
@location: Barranquilla, Colombia
"""
from time import mktime
from datetime import datetime

# Name of the log file.
LOG_FILE = "log.txt"

# Datetime format.
FORMAT = "%d %b %Y %I:%M:%S %p %Z"


class Logger:
    """ Log class that handles error messages.

        When an exception is raised, this class is in charge of registering it
        to a .txt file called "log.txt".

        Parameters
        ----------
        message : str
            Error message.
    """

    def __init__(self) -> object:
        pass

    def utc2local(self, utc: datetime) -> datetime:
        """ Converts UTC date to local time date.

            Parameters
            ----------
            utc : datetime
                Current date in UTC.

            Returns
            -------
            Datetime object that stores the current date in GMT+5 format.
        """
        epoch = mktime(utc.timetuple())
        offset = datetime.fromtimestamp(
            epoch) - datetime.utcfromtimestamp(epoch)
        return utc + offset

    def log(self) -> None:
        """ Writes a log entry to the log file. """
        with open(LOG_FILE, "a") as log:
            current_date = datetime.utcnow()
            gmt5_date = self.utc2local(current_date).strftime(FORMAT)
            day = datetime.now().strftime("%A")

            # Writes entry.
            log.write(f"{day}, {gmt5_date} GMT+5: {self.message}\n")
