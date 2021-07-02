# -*- coding: utf-8 -*-
"""
Created on Thursday, July 1, 22:42:05 GMT+5, 2021.

@author: Camilo Martínez
@location: Barranquilla, Colombia
"""
import re
from functools import reduce
import Levenshtein
from difflib import SequenceMatcher

from bs4 import BeautifulSoup
from requests import HTTPError, Session, get

from movies_advisor.utils.log import Logger

# Filmaffinity root URL
FILMAFFINITY_URL_ROOT = "https://www.filmaffinity.com/en/search.php?stext="

# IMDB sign-in URL
IMDB_SIGNIN_URL = "https://www.imdb.com/registration/signin?u=/"

class MoviesFinder:
    """Handles the parsing of the websites necessary to get the movies."""
    def __init__(self, movies: dict, imdb_credentials: dict, number_critics: int = 2):
        """
        Parameters
        ----------
        movies : dict
            Movies whose complete information will be found, where the key is
            the name and the value is the year.
        imdb_credentials: dict
            IMDB credentials to sign in. Keys = {'email', 'password'}.
        number_critics: int, optional
            Constant that defines the maximum number of critics to store.
            By default, 2.
        """
        self.movies = movies
        self.number_critics = number_critics
        self.imdb_credentials = imdb_credentials
        self._info = dict()
        self._logger = Logger()

    def complete_information(self, verbose: bool = False) -> None:
        """Completes the information of each movie.
        
        Parameters
        ----------
            verbose : bool, optional
                By default, False.
        """
        self._info = {
            movie_name: dict() for movie_name in self.movies
        }

        # For each movie, this will fill the previous dictionary with the
        # complete information taken from Film Affinity and IMDb.
        for movie, year in self.movies.items():
            if verbose:
                print(f"Completing {movie} ({year})... ", end="")
                
            self.get_useful_information_from_filmaffinity(movie, year)
            original_name = self._info[movie]["original name"].lower()
            self.get_useful_information_from_imdb(movie, original_name, year)
            
            if verbose:
                print("Done")

    def get_useful_information_from_filmaffinity(self, movie_name: str,
                                                 movie_year: str) -> dict:
        """Gets the original name of the movie, synopsis and critics.

        This useful information is stored in a dictionary, where the key 
        is the name of the movie and its value is another dictionary, 
        which contains the folowing values: original name, year, synopsis,
        critics, tomatometer and audience score. The synopsis is a string 
        and the critics is a list of strings. 

        Information provider: Film Affinity.

        Parameters
        ----------
        movie_name : str
            Name of the movie in theaters (probably in spanish).
        movie_year : str
            Release year of the movie.

        Returns
        -------
        useful_information : dict
            Useful information regarding the movie.
        """
        url_root = FILMAFFINITY_URL_ROOT

        # CREATION OF URL
        # Lowers each word of the list of words in the name of the movie.
        movie_name_words = list(
            map(lambda word: word.strip().lower(),
                movie_name.split(" ")))

        # Constructs a string composed of all the words inside the previous
        # list separated by a '-'.
        parsed_movie_name = reduce(
            lambda a, b: a + "-" + b,
            movie_name_words
        ) if len(movie_name_words) > 1 else movie_name_words[0]

        url = url_root + parsed_movie_name + "&stype=all"  # Actual URL
        
        soup = self.soup_from_url(url)

        # SCRAPING AND CONSTRUCTION OF DICTIONARY
        original_name = ""
        year = movie_year
        synopsis = ""
        critics = list()

        information_tag = soup.select('dl[class="movie-info"] > dd')

        # Tests if the movie is unique. If it is not, this will produce an
        # IndexError. If there are, then the actual movie is found using both
        # year and name.
        try:
            original_name = information_tag[0].text.strip()
        except IndexError as e:
            message = "Found more than 1 movie for " + \
                movie_name + ". Original exception: " + str(e)
            self._logger.log(message)

            # Looks for all the possible movies.
            possible_movies_tags = soup.find_all(
                "div", attrs={"class": "se-it mt"})

            for possible_movie_tag in possible_movies_tags:
                year_tag = possible_movie_tag.select('div[class="ye-w"]')
                title_tag = possible_movie_tag.select("a[href]")

                if title_tag[0].get("title").strip().lower() == \
                        movie_name.lower():
                    # Checks if the information provided by Film Affinity
                    # matches that found in Fandango. In case the name of the
                    # movie matches, but the year does not, this algorithm
                    # accepts it if and only if the year varies +/- 1 year.
                    if year_tag[0].text.strip() == year or (
                            int(year) - 1 <= int(year_tag[0].text.strip()) <=
                            int(year) + 1):

                        # RE-CREATION OF BEAUTIFUL SOUP
                        soup = self.soup_from_url(title_tag[0].get("href"))
                        information_tag = soup.select(
                            'dl[class="movie-info"] > dd')
                        original_name = information_tag[0].text.strip()
                        break

        # Gets the original name of the movie and formats it.
        original_name = self.clean_string(original_name)

        # Gets the synopsis of the movie and formats it.
        synopsis = soup.find(
            "dd", attrs={"itemprop": "description"}).text.strip()
        synopsis = self.clean_string(synopsis)
        synopsis += "." if not synopsis.endswith(".") else ""

        # Gets the critics of the movie and makes the necessary formatting
        # algorithms.
        critics_tags = soup.select('div[itemprop="reviewBody"]')

        if critics_tags:
            critics = [
                self.clean_string(critics_tag.text.strip())
                for index, critics_tag in enumerate(critics_tags)
                if index < self.number_critics
            ]

            critics = [critic + "."
                       if not critic.endswith(".") else critic
                       for critic in critics]

            critics = [critic.split("Rating")[0].strip()
                       if "Rating" in critic else critic
                       for critic in critics]
        else:  # In case the list is empty.
            critics = None

        # Constructing the useful information in the desired form and assign
        # it to its right key.
        d = {
            "original name": original_name,
            "year": year,
            "synopsis": synopsis,
            "critics": critics,
            "imdb_rating": None
        }

        self._info[movie_name] = d

    def get_useful_information_from_imdb(self, movie_name,
                                         original_movie_name: str,
                                         movie_year: str) -> float:
        """ Gets the IMDB rating of the movie by using the IMDb module.

            Parameters
            ----------
            movie_name : str
                Name of the movie in theaters (probably in spanish).
            original_movie_name : str
                Original name of the movie.
            movie_year : str
                Release year of the movie.

            Returns
            -------
            imdb_rating : float
                Useful information regarding the movie. 
        """
        s = self.sign_in_to_imdb()  # Gets current session. Signs in to IMDb.

        url_root = "https://www.imdb.com/find?q="

        # CREATION OF URL
        # Lowers each word of the list of words in the name of the movie.
        movie_name_words = original_movie_name.split(" ")

        # Constructs a string composed of all the words inside the previous
        # list separated by a '+'.
        parsed_movie_name = reduce(
            lambda a, b: a + "+" + b,
            movie_name_words
        ) if len(movie_name_words) > 1 else movie_name_words[0]

        # Actual URL.
        url = url_root + parsed_movie_name + "&ref_=nv_sr_sm"

        # Creation of BeautifulSoup object
        soup = self.soup_from_url(url, s)

        # Scraping and construction of dictionary
        search_item_tags = soup.find_all("td", attrs={"class": "result_text"})

        for item in search_item_tags:
            new_url = "https://www.imdb.com" + item.select("a[href]")[
                0].get("href")

            try:
                soup = self.soup_from_url(new_url, s)

                # First, it tries to find the original title. If it doesn't
                # exist, it takes the "normal" title.
                try:
                    current_movie_name = soup.find("div", attrs={
                        "class": "originalTitle"
                    }).text.strip().lower()\
                        .split("(original title)")[0].strip()
                except:
                    current_movie_name = soup.find("div", attrs={
                        "class": "title_wrapper"
                    }).select("h1").text.strip().lower()

                current_movie_year = soup.find("span", attrs={
                    "id": "titleYear"
                }).select("a[href]")[0].text.strip()

                if self.title_is_accurate(current_movie_name,
                                          original_movie_name) and \
                        current_movie_year == movie_year:
                    imdb_rating = soup.find("span", attrs={
                        "itemprop": "ratingValue"
                    }).text.strip()
                    self._info[movie_name][
                        "imdb_rating"] = imdb_rating
                    return
            except Exception as e:
                self._logger.log(str(e))

    def clean_string(self, string: str) -> str:
        """ Cleans the given string.

            Deletes unwanted characters like ", ', (...), '\' from the string.

            Parameters
            ----------
            string : str
                String to clean

            Returns
            -------
            cleaned_string : str
                Cleaned/Formatted string.
        """
        string = (
            string.replace('"', " ")
            .replace("'", " ")
            .replace("',", ", ")
            .replace("'", "")
            .replace(" (...) ", ". ")
            .replace(" (…) ", ". ")
            .replace("“", "")
            .replace("..", ". ")
            .replace(" ,", ", ")
            .replace("  ", " ")
            .strip()
        )

        if string.endswith("(FILMAFFINITY)"):
            string = string[:-14].strip()

        if string.endswith('aka'):
            string = string[:-3].strip()

        return string

    def find_year_in_unformatted_text(self, string: str) -> str:
        """ Finds the release year of a movie, whose name and year are in an 
            unformatted text.

            Example: 
            Star Wars: The Rise of Skywalker (2019) (TV Episode) - Season 2 
            IMDb on the Scene - Interviews (2017) (TV Series)

            Parameters
            ----------
            string : str
                Unformatted text.

            Returns
            -------
            year : str
                Release year.
        """
        possible_year = ""
        inside_parentheses = re.findall('\(.*?\)', string)
        for stuff in inside_parentheses:
            if stuff[1:-1].isdigit():
                possible_year = stuff[1:-1]
                break

        return possible_year

    def soup_from_url(self, url: str, s: Session = None) -> object:
        """ Gets the BeautifulSoup object from a url using the requests module.

        Headers are used for avoiding the error "exceeded 30 redirects".

        Parameters
        ----------
        url : str
            URL to get the BeautifulSoup object from.
        s : requests.Session
            Current session. Its default value is None.

        Returns
        -------
        soup : BeautifulSoup object
        """
        headers = {
            'Accept-Encoding': 'gzip, deflate, sdch',
            'Accept-Language': 'en-US,en;q=0.8',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent':
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like '
            'Gecko) Chrome/56.0.2924.87 Safari/537.36',
            'Accept':
            'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,'
            '*/*;q=0.8',
            'Cache-Control': 'max-age=0', 'Connection': 'keep-alive'
        }
        # Requests a connection to the website. If s is given, it requests
        # through the specified session.
        res = get(url, headers=headers) if s is None else s.get(url)

        try:  # In case something goes wrong.
            res.raise_for_status()
        except HTTPError as e:
            message = f"""An error ocurred while requesting to the website.
                          Original exception: {e}"""
            self._logger.log(message)

        soup = BeautifulSoup(res.text, features="html.parser")
        return soup

    def sign_in_to_imdb(self) -> Session:
        """Signs in to IMDb using the appropiate credentials.

        Returns
        -------
        s : requests.Session
            Current session.
        """
        signin_url = IMDB_SIGNIN_URL
        soup = self.soup_from_url(signin_url)
        sign_in_tag = soup.find('a', attrs={'class': 'list-group-item'})

        # Gets the actua sign in URL which lets the user sign in with an
        # IMDb account.
        signin_IMDB_url = sign_in_tag.get('href')

        s = Session()

        login_data = {
            'email': self.imdb_credentials["email"],
            'password': self.imdb_credentials["password"]
        }

        s.post(signin_IMDB_url, data=login_data)
        return s

    def title_is_accurate(self, title: str, original_title: str,
                          use_levenshtein: bool = True) -> bool:
        """Checks if the title is accurate according to the original title.

        The accuracy is defined as the ratio of words in title that are in
        the original title. If it is greater than or equal to 90%, the 
        given title is considered to be "accurate".

        Parameters
        ----------
        title : str
            The title to which its accuracy will be calculated.
        original_title : str
            Original title of the movie.
        use_levenshtein: bool, optional
            Whether to use Levenshtein distance or Python's built-in
            Sequence matcher. By default, True.

        Returns
        -------
        accuracy : float
            Accuracy of the given title. Float number between 0 and 1.0
        """
        if use_levenshtein:
            similarity = Levenshtein.ratio(title, original_title)
        else:
            similarity = SequenceMatcher(None, title, original_title).ratio()

        if similarity >= 0.9:
            return True
        else:
            return False
