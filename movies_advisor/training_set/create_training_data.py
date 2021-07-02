# -*- coding: utf-8 -*-
"""
Created on Thursday, July 1, 22:42:05 GMT+5, 2021.

@author: Camilo Martínez
@location: Barranquilla, Colombia
"""
import pandas as pd
from movies_advisor.movies_finder import MoviesFinder
import dateutil.parser
from dotenv import dotenv_values
from pathlib import Path
import os

def extract_year(date: str) -> int:
    return dateutil.parser.parse(date).year
    
def load_mcu_movies(file_: str = "MCU.csv") -> pd.DataFrame:
    mcu = pd.read_csv("MCU.csv", delimiter=",").applymap(
        lambda x: x.strip() if isinstance(x, str) else x
    )
    mcu.columns = mcu.columns.str.strip()
    mcu = mcu.rename(columns={"Release date": "Year"})
    mcu = mcu[mcu["Year"].notnull() & (mcu["Film/TV"] == "Film")].drop(["In-universe year", "Film/TV", "Phase"], axis=1)
    mcu["Year"] = mcu["Year"].apply(extract_year)
    return mcu

def load_imdb_credentials(credentials_file: str) -> dict:
    config = dotenv_values(credentials_file)
    config["email"] = config.pop("IMDB_EMAIL")
    config["password"] = config.pop("IMDB_PASS")
    return config

mcu = load_mcu_movies()
mcu_movies = pd.Series(mcu.Year.values, index=mcu.Title).to_dict()

credentials_file = os.path.join(Path(os.getcwd()).parents[1], "credentials.env")
imdb_credentials = load_imdb_credentials(credentials_file=credentials_file)

finder = MoviesFinder(mcu_movies, imdb_credentials)
finder.complete_information(verbose=True)
