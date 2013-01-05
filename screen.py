#! /usr/bin/python

# Welcome to the Dopeler Value Investing pre-screening tool.
# Yes, the name Dopeler is inspired by the movie _Snow Day_.

# Dopeler Value Investing only a pre-screening tool to identify the stocks that appear to be most promising.
# This is NOT a replacement for the more detailed Doppler Value Investing analysis.
# The purpose of Dopeler Value Investing is to quickly process financial information on thousands of stocks.
# Stocks that are clearly incompatible with the Doppler Value Investing philosophy can be quickly screened out.
# Attention can be focused on the most promising stocks.

# Please note that not all stocks that look attractive in the Dopeler Value Investing screen are suitable.
# Some may be beneficiaries of the high point in the industry cycle.
# Some may be the beneficiaries of a temporary fad.
# In addition, there may be other problems with some of these stocks.

import pwd
import sys
import os
import csv
import datetime
import signal
import urllib2
import time, random
import socket
import urllib
import lxml
import lxml.html
import re
import math

##########################################################################################
# PART 1: FIGURE OUT THE DIRECTORY STRUCTURE
# THIS IS NEEDED TO DISTINGUISH BETWEEN THE DEVELOPMENT ENVIRONMENT AND SERVER ENVIRONMENT
# THIS DETERMINES THE PATH TO CRITICAL DIRECTORIES AND FILES
##########################################################################################

# Assume that this is the server environment
dir_home = '/home/doppler' # Home directory on server
dir_screen = dir_home + '/webapps/scripts_doppler/dopplervalueinvesting'

# Check this assumption
is_server = os.path.exists(dir_home) # Determine if this is the server environment

# Adjustments to make if this is the development environment instead of the server environment
if not (is_server):
    # Get your username (not root)
    uname=pwd.getpwuid(1000)[0]
    dir_home = '/home/' + uname
    dir_screen = dir_home + '/dopplervalueinvesting'

# Determine the paths of critical directories
dir_input = dir_screen + '/screen-input'
dir_downloads = dir_screen + '/screen-downloads'
dir_output = dir_screen + '/screen-output'  

###############################################################################
# PART 2: DECIDE WHETHER TO ANALYZE ALL 5000+ STOCKS OR JUST A SMALL TEST GROUP
# (DEVELOPMENT ENVIRONMENT ONLY)
###############################################################################
run_long = True # By default, run the long version of the script
if not (is_server): # Offer a choice in the development environment
    print ("The long version of this script analyzes 5000+ stocks.")
    print ("The alternative is a quick version that just analyzes a few dozen stocks.")
    y_or_n = raw_input('Do you wish to run the long version?  (Y/N)\n')
    y_or_n = y_or_n.lower()
    if (y_or_n == 'y' or y_or_n == 'yes'):
        print "Running the long version"
    else:
        run_long = False
        print "Running the short version"

######################################################################################
# PART 3: DOWNLOAD THE LISTS OF AMEX, NYSE, AND NASDAQ STOCKS FROM THE NASDAQ WEB SITE
######################################################################################

# Get age of file
# Based on solution at 
# http://stackoverflow.com/questions/5799070/how-to-see-if-file-is-older-than-3-months-in-python
# Returns a billion if the file does not exist
def age_of_file (file1): # In hours
    now = datetime.datetime.now ()
    try:
        modified_date = datetime.datetime.fromtimestamp(os.path.getmtime(file1))
        age = now - modified_date
        age_days = age.days 
        age_seconds = age.seconds
        age_hours = 24 * age_days + age_seconds/3600
        return age_hours
    except:
        return 1000000000

class TimeoutException(Exception): 
    pass

def timeout_handler(signum, frame):
    raise TimeoutException()

# Download a page from a url and save it
# Only download if the existing page is at least 4 days old.
# If the download is not successful, make up to 2 additional attempts.
# Inputs: URL of source, path of destination
# Times out after 10 seconds
def download_page (url, file_name, file_age_max_hours):
    from urllib2 import Request, urlopen, URLError, HTTPError
    file_age = age_of_file (file_name) # In hours
    file_size = 0
    try:
        file_size = os.path.getsize (file_name)
    except:
        file_size = 0
    n_fail = 0
    n_fail_max = 2
    while ((file_age > file_age_max_hours or file_size == 0) and n_fail <= n_fail_max):
        try:
            f = urllib2.urlopen (url)
            local_file = open (file_name, 'w') # Open local file
            local_file.write (f.read())
            local_file.close ()
            time.sleep (random.uniform (.1, .2)) # Delay is needed to limit the impact on the upstream server
            break # Script hangs without this command
        except urllib2.HTTPError, e:
            n_fail = n_fail + 1
            print "Failure #: " + str (n_fail)
            print "HTTP Error:",e.code , url
        except urllib2.URLError, e:
            n_fail = n_fail + 1
            print "Failure #: " + str (n_fail)
            print "URL Error:",e.reason , url
        except Exception,e: 
            n_fail = n_fail + 1
            print "Failure #: " + str (n_fail)
            print str(e)
    if n_fail > n_fail_max:
        print "Download failed, giving up"
    if file_age <= file_age_max_hours and file_size > 0:
        print "Local file is new enough - skipping download"

# Purpose: download the CSV file listing all stocks on the exchange
# http://www.nasdaq.com/screening/companies-by-industry.aspx?exchange=NASDAQ&render=download
if run_long:
    URL_BASE_NASDAQ = 'http://www.nasdaq.com/screening/companies-by-industry.aspx?exchange='
    URL_END_NASDAQ = '&render=download'

    url1 = URL_BASE_NASDAQ + 'AMEX' + URL_END_NASDAQ
    url2 = URL_BASE_NASDAQ + 'NYSE' + URL_END_NASDAQ
    url3 = URL_BASE_NASDAQ + 'NASDAQ' + URL_END_NASDAQ

    file1 = dir_input + '/companylist-amex.csv'
    file2 = dir_input + '/companylist-nyse.csv'
    file3 = dir_input + '/companylist-nasdaq.csv'
    file_age_max_hours = 12

    print ('Downloading list of AMEX stocks')
    download_page (url1, file1, file_age_max_hours)
    print ('Downloading list of NYSE stocks')
    download_page (url2, file2, file_age_max_hours)
    print ('Downloading list of NASDAQ stocks')
    download_page (url3, file3, file_age_max_hours)

##############################################################################################
# PART 4: For a given exchange, obtain a list of ticker symbols for stocks that are NOT funds.
##############################################################################################

# Purpose: extract a given column from a 2-D list
# Input: 2-D data list
# Output: 1-D data list representing the (n_local+1) -th column of the input list
def column (list_input, n_input):
    list_transpose = zip (*list_input)
    return list_transpose [n_input]

# Purpose: extract a given column from a 2-D list but omit the top row
# Input: 2-D data list
# Output: 1-D data list representing the (n_local+1) -th column of the input list, minus the first entry
def column_data (list_input, n_input):
    list1 = column (list_input, n_input)
    list2 = list1 [1:]
    return list2

# Purpose: count the number of columns in a 2-D list
# Input: 2-D data list
# Output: integer representing the number of columns of the 2-D list
def num_of_columns (list_input):
    list_transpose = zip (*list_input)
    n_local = len (list_transpose)
    return n_local

# Purpose: get the first row in a 2-D list
# Input: 2-D data list
# Output: 1-D data list
def list_titles (list_input):
    list_output = list_input [0][0:]
    return list_output

# Purpose: get the column number corresponding to a title
# Input: 2-D data list
# Output: integer
def col_num_title (list_input, string_input):
    list_1d = list_titles (list_input)
    n = 0
    n_final = len (list_1d) - 1
    while n <= n_final:
        if (list_1d [n] == string_input):
            return n
        n = n + 1
    return None 

# Purpose: get the column corresponding to a title
# Input: 2-D data list
# Output: 1-D data list of strings
def col_title (list_input, string_input):
    col_num_local = col_num_title (list_input, string_input)
    list_output = column_data (list_input, col_num_local) 
    return list_output

# Purpose: Convert a string to a floating point number
# Input: string
# Output: floating point number
def str_to_float (string_input):
    try:
        x = float (string_input)
    except:
        x = None
    return x

# This defines the class CSVfile (filename).
# Input: name of csv file
# Output: 2-D list fed by the input file
class CSVfile:
    def __init__ (self, filename):
        self.filename = filename

    def filelist (self):
        locallist = []
        with open (self.filename, 'rb') as f:
            reader = csv.reader (f, delimiter = ',', quotechar = '"', quoting = csv.QUOTE_MINIMAL)
            for row in reader:
                locallist.append (row)
        return locallist

# This defines the class Exchange (exch_abbrev)
# Input: 'nyse', 'amex', or 'nasdaq'
# Outputs: 2-D data list
class Exchange:
    def __init__ (self, exch_abbrev):
        self.exch_abbrev = exch_abbrev

    # Purpose: reads the contents of the file containing the list of stocks and information on each stock
    # Input: file containing list of stocks
    # Output: 2-D data list
    def data (self):
        file_stock = CSVfile (dir_input + '/companylist-' + self.exch_abbrev + '.csv')
        list_stock = file_stock.filelist ()
        return list_stock

    # Purpose: get list of all entries in a column with a given title
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def column_all (self, string_input):
        list_input = self.data ()
        list_titles_local = list_titles (list_input)
        num_col_symbol = col_num_title (list_input, string_input)
        list_output = column_data (list_input, num_col_symbol)
        return list_output
        
    # Purpose: get a list of the symbols for all of the stocks profiled
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def symbol_all (self):
        list1 = self.data ()
        list_output = col_title (list1, 'Symbol')
        return list_output

    # Purpose: get a list of the sectors for each stock
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def sector_all (self):
        list1 = self.data ()
        list_output = col_title (list1, 'Sector')
        return list_output

    # Purpose: get a list of the industries for each stock
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def industry_all (self):
        list1 = self.data ()
        list_output = col_title (list1, 'Industry')
        return list_output

    # Purpose: get a list of the names for each stock
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def name_all (self):
        list1 = self.data ()
        list_output = col_title (list1, 'Name')
        return list_output

    # Purpose: get a list of the prices for each stock
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def price_all (self):
        list1 = self.data ()
        list_output = col_title (list1, 'LastSale')
        return list_output

    # Purpose: get a list of the market caps for each stock
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def marketcap_all (self):
        list1 = self.data ()
        list_output = col_title (list1, 'MarketCap')
        return list_output

    # Purpose: get a list of the index number for each stock
    # Input: 2-D data list containing all information in the file
    # Output: 1-D data list
    def index_all (self):
        list1 = self.data ()
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        list_output = []
        while n <= n_last:
            list_output.append (n)
            n = n + 1
        return list_output

    # Purpose: get a list of the index numbers for each stock that is NOT a fund
    # Inputs: 1-D data lists 
    # Output: 1-D data list
    def index_selected (self):
        list1 = self.sector_all ()
        list2 = self.industry_all ()
        list3 = self.index_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        list_output = []
        while n <= n_last:
            if (list1 [n] <> "n/a" ) & (list2 [n] <> "n/a" ):
                list_output.append (list3 [n])
            n = n + 1
        return list_output

    # Purpose: get a list of the ticker symbols for each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list 
    def symbol_selected (self):
        list1 = self.index_selected ()
        list2 = self.symbol_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            i_select = list1 [n]
            symbol1 = list2 [i_select]
            symbol1 = symbol1.replace (' ', '') # Eliminate spaces
            symbol1 = symbol1.replace ('/', '.') # Replace slash with period
            list_output.append (symbol1) 
            n = n + 1
        return list_output

    # Purpose: get a list of the names of each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list
    def name_selected (self):
        list1 = self.index_selected ()
        list2 = self.name_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            i_select = list1 [n]
            name1 = list2 [i_select]
            name1 = name1.replace ("&#39;", "'") # Replace &#39; with '
            list_output.append (name1) 
            n = n + 1
        return list_output

    # Purpose: get a list of the prices of each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list of numbers
    def price_selected (self):
        list1 = self.index_selected ()
        list2 = self.price_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            i_select = list1 [n]
            price_str = list2 [i_select]
            price_num = str_to_float (price_str)
            list_output.append (price_num) 
            n = n + 1
        return list_output

    # Purpose: get a list of the market caps of each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list of numbers
    def marketcap_selected (self):
        list1 = self.index_selected ()
        list2 = self.marketcap_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            i_select = list1 [n]
            marketcap_str = list2 [i_select]
            marketcap_num = str_to_float (marketcap_str)
            list_output.append (marketcap_num) 
            n = n + 1
        return list_output

    # Purpose: get a list of the number of shares outstanding for each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list of numbers
    def nshares_selected (self):
        list1 = self.marketcap_selected ()
        list2 = self.price_selected ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            marketcap1 = list1 [n]
            price1 = list2 [n]
            try:
                nshares1 = round(marketcap1/price1)
            except:
                nshares1 = None
            list_output.append (nshares1) 
            n = n + 1
        return list_output

    # Purpose: get a list of the sectors of each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list
    def sector_selected (self):
        list1 = self.index_selected ()
        list2 = self.sector_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            i_select = list1 [n]
            sector1 = list2 [i_select]
            list_output.append (sector1) 
            n = n + 1
        return list_output

    # Purpose: get a list of the industries of each stock that is NOT a fund
    # Inputs: 1-D data lists
    # Output: 1-D data list
    def industry_selected (self):
        list1 = self.index_selected ()
        list2 = self.industry_all ()
        list_output = []
        n_length = len (list1)
        n_last = n_length -1
        n = 0
        while n <= n_last:
            i_select = list1 [n]
            industry1 = list2 [i_select]
            list_output.append (industry1) 
            n = n + 1
        return list_output

#######################################################################################################################
# PART 5: Using Exchange.symbol_selected, compile the list of ticker symbols from the AMEX, NYSE, and NASDAQ exchanges.
#######################################################################################################################
print "******************************"
print "BEGIN acquiring list of stocks"

# BEGIN: this section is for testing purposes

Exchange1 = Exchange ('test')
list_symbol = Exchange1.symbol_selected ()
list_name = Exchange1.name_selected ()
list_price = Exchange1.price_selected ()
list_nshares = Exchange1.nshares_selected ()
list_sector = Exchange1.sector_selected ()
list_industry = Exchange1.industry_selected ()

# END: this section is for testing purposes

# BEGIN: enable this section for analyzing all AMEX, NYSE, and NASDAQ stocks
if run_long:
    Exchange1 = Exchange ('amex')
    Exchange2 = Exchange ('nasdaq')
    Exchange3 = Exchange ('nyse')

    list_symbol = Exchange1.symbol_selected () + Exchange2.symbol_selected () + Exchange3.symbol_selected ()
    list_name = Exchange1.name_selected () + Exchange2.name_selected () + Exchange3.name_selected ()
    list_price = Exchange1.price_selected () + Exchange2.price_selected () + Exchange3.price_selected ()
    list_nshares = Exchange1.nshares_selected () + Exchange2.nshares_selected () + Exchange3.nshares_selected ()
    list_sector = Exchange1.sector_selected () + Exchange2.sector_selected () + Exchange3.sector_selected ()
    list_industry = Exchange1.industry_selected () + Exchange2.industry_selected () + Exchange3.industry_selected ()

# END: enable this section for analyzing all AMEX, NYSE, and NASDAQ stocks

num_stocks = len (list_symbol)
print "Total number of stocks: " + str(num_stocks)
print "FINISHED acquiring list of stocks"
print "*********************************"

############################################################
# PART 6: For each stock, download the financial data needed
############################################################
# NOTE: Downloading is bypassed if the file to be replaced is less than 4 days old.  
# NOTE: Delay is used to avoid overwhelming the servers.

# Getting financial figures from CNBC (more data than Yahoo, capable of handling big loads)
URL_BASE_SMARTMONEY = 'http://www.smartmoney.com/quote/'
URL_BASE_YAHOO = "http://finance.yahoo.com/q/"
LOCAL_BASE = dir_downloads

# Smart Money URL for balance sheet data
def url_balancesheet (symbol1):
    url1 = URL_BASE_SMARTMONEY + symbol1 
    url1 = url1 + '/?story=financials&timewindow=1&opt=YB&isFinprint=1&framework.view=smi_emptyView'
    return url1

# Smart Money URL for income statement data
def url_income (symbol1):
    url1 = URL_BASE_SMARTMONEY + symbol1
    url1 = url1 + '/?story=financials&timewindow=1&opt=YI&isFinprint=1&framework.view=smi_emptyView'
    return url1

# Smart Money URL for cash flow statement data
def url_cashflow (symbol1):
    url1 = URL_BASE_SMARTMONEY + symbol1
    url1 = url1 + '/?story=financials&timewindow=1&opt=YC&isFinprint=1&framework.view=smi_emptyView'
    return url1

# Yahoo Finance URL for income statement data
def url_income_yahoo (symbol1):
    url1 = URL_BASE_YAHOO + 'is?s=' + symbol1 + '+Income+Statement&annual'
    return url1

# Yahoo Finance URL for income statement data
def url_balancesheet_yahoo (symbol1):
    url1 = URL_BASE_YAHOO + 'bs?s=' + symbol1 + '&annual'
    return url1

def local_root (symbol1):
    url1 = LOCAL_BASE + '/' + symbol1
    return url1

def local_balancesheet (symbol1):
    url1 = local_root (symbol1) + '/balancesheet.html'
    return url1

def local_income (symbol1):
    url1 = local_root (symbol1) + '/income.html'
    return url1

def local_cashflow (symbol1):
    url1 = local_root (symbol1) + '/cashflow.html'
    return url1

def local_income_yahoo (symbol1):
    url1 = local_root (symbol1) + '/income-yahoo.html'
    return url1

def local_balancesheet_yahoo (symbol1):
    url1 = local_root (symbol1) + '/balancesheet-yahoo.html'
    return url1


# Create directory path1 if it does not already exist
def create_dir (path1):
    if not (os.path.exists(path1)):
        os.mkdir (path1)

# Download information on a given stock
def download_data_stock (symbol1, file_age_max_hours):
    url1 = url_balancesheet (symbol1)
    url2 = url_income (symbol1)
    url3 = url_cashflow (symbol1)
    url4 = url_balancesheet_yahoo (symbol1)
    url5 = url_income_yahoo (symbol1)
    local1 = local_balancesheet (symbol1)
    local2 = local_income (symbol1)
    local3 = local_cashflow (symbol1)    
    local4 = local_balancesheet_yahoo (symbol1)
    local5 = local_income_yahoo (symbol1)

    # NOTE: Alternating between downloading from Smartmoney and downloading from Yahoo Finance
    # to limit impact on their servers
    print "Downloading data on " + symbol1
    print "Downloading balance sheet data"
    download_page (url1, local1, file_age_max_hours)

    print "Downloading Yahoo balance sheet data"
    download_page (url4, local4, file_age_max_hours)

    print "Downloading income statement data"
    download_page (url2, local2, file_age_max_hours)

    print "Downloading Yahoo income data"
    download_page (url5, local5, file_age_max_hours)

    print "Downloading cash flow data"
    download_page (url3, local3, file_age_max_hours)
    
create_dir (LOCAL_BASE) # Create screen-downloads directory if it does not already exist
i_stock = 0
i_stock_max = len (list_symbol)
start = time.time ()
for symbol in list_symbol:
    create_dir (local_root (symbol)) # Create directory for stock if it does not already exist
    max_age_hours = 168
    download_data_stock (symbol, max_age_hours)
    i_stock = i_stock + 1

    now = time.time ()
    t_elapsed = now - start
    try:
        rate_s = i_stock / t_elapsed # Stocks/second
        remain_s = (i_stock_max - i_stock)/rate_s
        remain_m = int (round(remain_s/60))
        print "Download completion: " + str(i_stock) + '/' + str(i_stock_max) + "; Minutes remaining: " + str(remain_m)
    except:
        pass

    
###############################################################
# PART 7: For each stock, process the financial data downloaded
###############################################################

# Purpose: Remove the HTML tags, commas, and spaces from an element in a list; used for processing financial data
# Input: 1-D list of BeautifulSoup.Tag
# Output: 1-D list of numbers
def clean_list (list_input):
    list_output = []
    n_length = len (list_input)
    n_last = n_length -1
    n = 0
    while n <= n_last:
        item_string = list_input [n]
        item_string = item_string.replace (' ', '') # Eliminate spaces
        item_string = item_string.replace ('\t', '') # Eliminate tabs
        item_string = item_string.replace ('\n', '') # Eliminate newlines
        item_string = item_string.replace (',', '') # Eliminate commas
        item_string = re.sub('<[^<]+?>', '', item_string) # Eliminate HTML tags
        item_float = str_to_float (item_string)
        list_output.append (item_float)
        n = n + 1            
    return list_output

# Purpose: Determine the units in the page (thousands of dollars or millions of dollars)
# Input: string
# Output: number
def get_units (string_html):
    str_thousands = "Figures in thousands of U.S. Dollars"
    str_thousands_alt = "All numbers in thousands" # Yahoo
    str_millions = "Figures in millions of U.S. Dollars"
    str_millions_alt = "All numbers in millions" # Yahoo
    str_billions = "Figures in billions of U.S. Dollars"
    str_billions_alt = "All numbers in billions" # Yahoo
    if (str_thousands in string_html) or (str_thousands_alt in string_html):
        return 1E3
    elif (str_millions in string_html) or (str_millions_alt in string_html):
        return 1E6
    elif (str_billions in string_html) or (str_billions_alt in string_html):
        return 1E9
    else:
        return None

# Purpose: Determine the dB value of a positive number
# Input: number
# Output: number
def db (num_input):
    num_output = 0
    try:
        num_output = 10 * math.log10 (num_input)
    except:
        num_output = None
    return num_output
    
# Purpose: Determine the average of a list of numbers
# Input: list of numbers
# Output: number
def ave (list_input):
    num_output = 0
    try:
        num_output = sum (list_input) / len (list_input)
    except:
        num_output = None
    return num_output

# Purpose: Get the square of a number
def square (num_input):
    num_output = 0
    try:
        num_output = math.pow (num_input, 2)
    except:
        num_output = None
    return num_output

# Purpose: Determine the sample variance of a list of numbers
# Input: list of numbers
# Output: number
def variance (list_input):
    num_output = 0
    try:
        num_ave = ave (list_input)
        sum_squared_dev = 0
        n_length = len (list_input)
        i_max = n_length - 1
        i = 0
        while i <= i_max:
            n = list_input [i]
            squared_dev = square (n - num_ave)
            sum_squared_dev = sum_squared_dev + squared_dev
            i = i + 1
        num_output = sum_squared_dev / (n_length - 1)
    except:
        num_output = None
    return num_output

# Purpose: Determine the sample standard deviation of a list of numbers
# Input: list of numbers
# Output: number
def std_dev (list_input):
    num_output = 0
    try:
        num_output = math.sqrt (variance (list_input))
    except:
        num_output = None
    return num_output

list_roe_ave = []
list_roe0 = []
list_roe1 = []
list_roe2 = []
list_roe3 = []
list_eps = []
list_netliq_ps = []
list_intrinsic_ps = []
list_pe = []
list_yield = []
list_pb = []
list_assets_smartmoney = []
list_assets_yahoo = []
list_assets_ratio = []
list_assets_suspect = []
list_rev_smartmoney = []
list_rev_yahoo = []
list_rev_ratio = []
list_rev_suspect = []
list_ppe_growth = []
list_ppe_growth_dev = []
list_ppe_suspect = []
list_roe_dev = []
list_roe_lowball = []
list_roe_low = []
list_iv_none = []

i_stock = 0
i_stock_max = len (list_symbol)
start = time.time ()
for symbol in list_symbol:
    print "Analyzing " + symbol

    # SPECIAL THANKS to root on stackoverflow.com for help on how to parse a row from the Smartmoney pages.
    # SPECIAL THANKS to MRAB on comp.lang.python and soulseekah on stackoverflow.com for help on how to parse a 
    # row from the Yahoo Finance pages.

    # PARSE DATA FROM BALANCE SHEET
    list_cash = []
    list_ppe = []
    list_liab = []
    list_ps = []
    list_assets = []
    units_balancesheet = 0

    try:
        url_local = local_balancesheet (symbol)
        url_local = "file://" + url_local
        result = urllib.urlopen(url_local)
        element_html = result.read()
        doc = lxml.html.document_fromstring (element_html)

        units_balancesheet = get_units (element_html)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Cash & Short Term Investments")]]/following-sibling::td/text()')
        list_cash = clean_list (list_row)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Property, Plant & Equipment - Gross")]]/following-sibling::td/text()')
        list_ppe = clean_list (list_row)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Total Liabilities")]]/following-sibling::td/text()')
        list_liab = clean_list (list_row)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Preferred Stock (Carrying Value)")]]/following-sibling::td/text()')
        list_ps = clean_list (list_row)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Total Assets")]]/following-sibling::td/text()')
        list_assets = clean_list (list_row)

    except:
        print "Balance sheet data not found"

    # PARSE DATA FROM BALANCE SHEET (YAHOO)
    list_assets_alt = []
    units_balancesheet_alt = 0
    try:
        url_local = local_balancesheet_yahoo (symbol)
        url_local = "file://" + url_local
        result = urllib.urlopen(url_local)
        element_html = result.read()
        doc = lxml.html.document_fromstring (element_html)

        units_balancesheet_alt = get_units (element_html)

        list_row = doc.xpath(u'.//td[strong[contains (text(),"Total Assets")]]/following-sibling::td/strong/text()') 
        list_assets_alt = clean_list (list_row)

    except:
        print "Yahoo Finance balance sheet data not found"

    # PARSE DATA FROM CASH FLOW STATEMENT
    list_cfo = [] # Cash flow from operations
    units_cashflow = 0
    
    try:
        url_local = local_cashflow (symbol)
        url_local = "file://" + url_local
        result = urllib.urlopen(url_local)
        element_html = result.read()
        doc = lxml.html.document_fromstring (element_html)

        units_cashflow = get_units (element_html)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Net Operating Cash Flow")]]/following-sibling::td/text()')
        list_cfo = clean_list (list_row)
    except:
        print "Cash flow data not found"

    # PARSE DATA FROM INCOME STATEMENT
    list_tax = [] # Income tax expense
    list_rev = [] # Revenue
    units_income = 0
    
    try:
        url_local = local_income (symbol)
        url_local = "file://" + url_local
        result = urllib.urlopen(url_local)
        element_html = result.read()
        doc = lxml.html.document_fromstring (element_html)

        units_income = get_units (element_html)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Income Tax")]]/following-sibling::td/text()')
        list_tax = clean_list (list_row)

        list_row = doc.xpath(u'.//th[div[contains (text(), "Sales/Revenue")]]/following-sibling::td/text()')
        list_rev = clean_list (list_row)
    except:
        print "Income statement data not found"

    # PARSE DATA FROM INCOME SHEET (YAHOO)
    list_rev_alt = []
    units_rev_alt = 0
    try:
        url_local = local_income_yahoo (symbol)
        url_local = "file://" + url_local
        result = urllib.urlopen(url_local)
        element_html = result.read()
        doc = lxml.html.document_fromstring (element_html)

        units_income_alt = get_units (element_html)

        list_row = doc.xpath(u'.//td[strong[contains (text(),"Total Revenue")]]/following-sibling::td/strong/text()') 
        list_rev_alt = clean_list (list_row)

    except:
        print "Yahoo Finance balance sheet data not found"


    # last year's PPE (at end of year) = PPE at the start of this year
    # this year's pre-tax free cash flow = This year's after-tax free cash flow + this year's income taxes
    # this year's after-tax free cash flow = this year's after-tax cash flow - this year's normalized capital spending
    # ASSUMPTION: this year's normalized capital spending = 10% of last year's PPE (at cost)
    # after-tax cash flow = official cash flow from operations
    # THUS:
    # this year's Dopeler earnings = this year's official cash flow from operations + this year's income taxes
    # - .1 * last year's PPE
    # this year's Dopeler Return On Equity = this year's Dopeler earnings / last year's PPE
    
    roe_ave = 0 # average Dopeler Return On Equity for the last 4 years
    cfo0 = 0
    cfo1 = 0
    cfo2 = 0
    cfo3 = 0
    cfo4 = 0

    try:
        cfo0 = list_cfo [0] * units_cashflow
    except:
        cfo0 = None
        
    try:
        cfo1 = list_cfo [1] * units_cashflow
    except:
        cfo1 = None

    try:
        cfo2 = list_cfo [2] * units_cashflow
    except:
        cfo2 = None

    try:
        cfo3 = list_cfo [3] * units_cashflow
    except:
        cfo3 = None

    try:
        cfo4 = list_cfo [4] * units_cashflow
    except:
        cfo4 = None

    tax0 = 0
    tax1 = 0
    tax2 = 0
    tax3 = 0
    tax4 = 0

    try:
        tax0 = list_tax [0] * units_income
    except:
        tax0 = None
    try:
        tax1 = list_tax [1] * units_income
    except:
        tax1 = None
    try:
        tax2 = list_tax [2] * units_income
    except:
        tax2 = None
    try:
        tax3 = list_tax [3] * units_income
    except:
        tax3 = None
    try:
        tax4 = list_tax [4] * units_income
    except:
        tax4 = None

    ppe0 = 0
    ppe1 = 0
    ppe2 = 0
    ppe3 = 0
    ppe4 = 0

    try:
        ppe0 = list_ppe [0] * units_balancesheet
    except:
        ppe0 = None
    try:
        ppe1 = list_ppe [1] * units_balancesheet
    except:
        ppe1 = None
    try:
        ppe2 = list_ppe [2] * units_balancesheet
    except:
        ppe2 = None
    try:
        ppe3 = list_ppe [3] * units_balancesheet
    except:
        ppe3 = None
    try:
        ppe4 = list_ppe [4] * units_balancesheet
    except:
        ppe4 = None
    
    roe0 = 0
    roe1 = 0
    roe2 = 0
    roe3 = 0
    roe_ave = 0

    try:    
        roe0 = (cfo0 + tax0 - .1 * ppe1) / ppe1
    except:
        roe0 = None

    try:
        roe1 = (cfo1 + tax1 - .1 * ppe2) / ppe2
    except:
        roe1 = None

    try:
        roe2 = (cfo2 + tax2 - .1 * ppe3) / ppe3
    except:
        roe2 = None

    try:
        roe3 = (cfo3 + tax3 - .1 * ppe4) / ppe4
    except:
        roe3 = None
        
    try:
        roe_ave = (roe0 + roe1 + roe2 + roe3)/4
    except:
        roe_ave = None
                
    list_roe_ave.append (roe_ave)
    list_roe0.append (roe0)
    list_roe1.append (roe1)
    list_roe2.append (roe2)
    list_roe3.append (roe3)

    # this year's projected Dopeler Earnings = last year's PPE * average Dopeler Return On Equity for the last 4 years
    earn = 0
    try:
        earn = roe_ave * ppe0
    except:
        earn = None
    
    # net liquidity = cash and short term investments - official total liabilities - preferred stock
    netliq = 0
    try:
        liq0 = list_cash [0] * units_balancesheet
        liab0 = list_liab [0] * units_balancesheet
        ps0 = list_ps [0] * units_balancesheet
        netliq = liq0 - liab0 - ps0
    except:
        netliq = None

    nshares = list_nshares [i_stock] # Number of shares outstanding
    
    # Dopeler earnings per share
    earn_ps = 0
    try:
        earn_ps = earn / nshares
    except:
        earn_ps = None
    list_eps.append (earn_ps)

    # Net liquidity per share
    netliqps = 0
    try:
        netliqps = netliq / nshares
    except:
        netliqps = None
    list_netliq_ps.append (netliqps)

    # Intrinsic value per share
    intrinsic_ps = 0
    try:
        intrinsic_ps = 10 * earn_ps + netliqps
    except:
        intrinsic_ps = None
    list_intrinsic_ps.append (intrinsic_ps)

    # Price
    price = list_price [i_stock]

    # Dopeler price/book
    pb = 0
    try:
        pb = price/intrinsic_ps
        if intrinsic_ps < 0:
            pb = None
    except:
        pb = None
    list_pb.append (pb)

    # Dopeler PE
    pe = 0
    try:
        pe = (price - netliqps) / earn_ps
        if earn_ps < 0:
            pe = None
    except:
        pe = None
    list_pe.append (pe)

    # Dopeler Yield
    yld = 0
    try:
        yld = earn_ps / (price - netliqps)
        if earn_ps < 0:
            yld = None
    except:
         yld = None
    list_yield.append (yld)


    ########################################################################
    # FILTERING CRITERIA: FLAG STOCKS THAT HAVE BAD DATA OR ARE INCOMPATIBLE
    ########################################################################

    # Check for asset value difference between Smartmoney and Yahoo Finance
    assets0 = 0
    try:
        assets0 = list_assets[0] * units_balancesheet / 1E9
    except:
        assets0 = None
    list_assets_smartmoney.append (assets0)

    assets0_alt = 0
    try:
        assets0_alt = list_assets_alt[0] * units_balancesheet_alt / 1E9
    except:
        assets0_alt = None
    list_assets_yahoo.append (assets0_alt)

    assets_ratio = 0
    try:
        assets_ratio = abs (db (assets0 / assets0_alt)) # dB
    except:
        assets_ratio = None
    list_assets_ratio.append (assets_ratio)

    # If the Smartmoney and the Yahoo Finance asset figures differ by 2 dB or more, suspect bad data.
    assets_suspect = False
    if assets_ratio >= 2 or assets_ratio == None:
        assets_suspect = True
    list_assets_suspect.append (assets_suspect)

    # Check for revenue difference between Smartmoney and Yahoo Finance
    rev0 = 0
    try:
        rev0 = list_rev[0] * units_income / 1E9
    except:
        rev0 = None
    list_rev_smartmoney.append (rev0)

    rev0_alt = 0
    try:
        rev0_alt = list_rev_alt[0] * units_income_alt / 1E9
    except:
        rev0_alt = None
    list_rev_yahoo.append (rev0_alt)

    rev_ratio = 0
    try:
        rev_ratio = abs (db (rev0 / rev0_alt)) # dB
    except:
        rev_ratio = None
    list_rev_ratio.append (rev_ratio)

    # If the Smartmoney and the Yahoo Finance revenue figures differ by 2 dB or more, suspect bad data.
    rev_suspect = False
    if rev_ratio >= 2 or rev_ratio == None:
        rev_suspect = True
    list_rev_suspect.append (rev_suspect)
    
    ppe0_db = 0
    ppe1_db = 0
    ppe2_db = 0
    ppe3_db = 0
    ppe_growth = 0
    ppe_growth_dev = 0
    try:
        ppe0_db = db (ppe0/ppe1)
        ppe1_db = db (ppe1/ppe2)
        ppe2_db = db (ppe2/ppe3)
        ppe3_db = db (ppe3/ppe4)
        ppe_growth = ave ([ppe0_db, ppe1_db, ppe2_db, ppe3_db]) # dB
        ppe_growth_dev = std_dev ([ppe0_db, ppe1_db, ppe2_db, ppe3_db]) # dB
    except:
        ppe_growth = None
        ppe_growth_dev = None
    list_ppe_growth.append (ppe_growth)
    list_ppe_growth_dev.append (ppe_growth_dev)

    # If the standard deviation of the PPE growth is at least 1 dB, suspect bad data.
    ppe_suspect = False
    if ppe_growth_dev >= 1 or ppe_growth_dev == None:
        ppe_suspect = True
    list_ppe_suspect.append (ppe_suspect)

    # Get relative standard deviation of Dopeler ROE
    roe_dev = 0
    try:
        roe_dev = std_dev ([roe0, roe1, roe2, roe3]) / roe_ave
        roe_dev = abs (roe_dev)
    except:
        roe_dev = None
    list_roe_dev.append (roe_dev)

    # Get lowest Dopeler ROE
    roe_min = 0
    try:
        roe_min = min (roe0, roe1, roe2, roe3)
    except:
        roe_min = None

    # Get lowball Dopeler ROE (lowest Dopeler ROE or 1 standard deviation below average, whichever is greater)
    # This ensures that the lowball Dopeler ROE is never lower than the lowest Dopeler ROE.

    # Example 1: Given a set of (1, 1, 1, 2), the average is 1.25, and the sample standard deviation is .5.
    # The lowest value is 1, but 1 standard deviation below average is only 0.75.
    # The lowball value is 1.

    # Example 2: Given a set of (1, 1, 1, 1), the average is 1, and the sample standard deviation is 0.
    # The lowest value is 1, but 1 standard deviation below average is 1.
    # The lowball value is 1.

    # Example 3: Given a set of (1, 1, 1, 0), the average is .75, and the sample standard deviation is .5.
    # The lowest value is 0, and 1 standard deviation below average is .25.
    # The lowball value is 0.25.

    roe_lowball = 0
    try:
        roe_lowball = max (roe_min, roe_ave - roe_dev)
    except:
        roe_lowball = None
    list_roe_lowball.append (roe_lowball)

    # If the lowball Dopeler ROE is under 10%, this is too low to be compatible with Doppler Value Investing.
    # to be compatible with Doppler Value Investing.
    roe_low = False
    if roe_lowball <.1 or roe_lowball == None:
        roe_low = True
    list_roe_low.append (roe_low)

    # If there is no intrinsic value or negative intrinsic value, this stock is not compatible with Doppler
    # Value Investing.
    iv_none = False
    if intrinsic_ps <=0 or intrinsic_ps == None:
        iv_none = True
    list_iv_none.append (iv_none)


    i_stock = i_stock + 1
    now = time.time ()
    t_elapsed = now - start
    rate_s = i_stock / t_elapsed # Stocks/second
    remain_s = (i_stock_max - i_stock)/rate_s
    remain_m = int (round(remain_s/60))
    print "Analysis completion: " + str(i_stock) + '/' + str(i_stock_max) + "; Minutes remaining: " + str(remain_m)

######################################################
# PART 7: PRINT THE RESULTS (UNFILTERED) TO A CSV FILE
######################################################

# Round a number to the nearest thousandth, convert to a string
# Input: number
# Output: string
def dec_thou (num_input):
    str_output = ''
    try:
        str_output = '{0:.3f}'.format(num_input)
    except:
        str_output = 'N/A'
    return str_output

# Round a number to the nearest hundredth, convert to a string
# Input: number
# Output: string
def dec_hund (num_input):
    str_output = ''
    try:
        str_output = '{0:.2f}'.format(num_input)
    except:
        str_output = 'N/A'
    return str_output

# Round a number to the nearest tenth, convert to a string
# Input: number
# Output: string
def dec_tenth (num_input):
    str_output = ''
    try:
        str_output = '{0:.1f}'.format(num_input)
    except:
        str_output = 'N/A'
    return str_output

# Round a number to the nearest .1%, convert to a string
# Input: number
# Output: string
def percent_tenth (num_input):
    str_output = ''
    try:
        str_output = '{0:.1%}'.format(num_input)
    except:
        str_output = 'N/A'
    return str_output



i_stock = 0
i_stock_max = len (list_symbol) -1
create_dir (dir_output) # Create output directory if it does not already exist
filename_output = dir_output + "/results-unfiltered.csv"

with open(filename_output, 'w') as csvfile:
    resultswriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    h1 = 'Symbol'
    h2 = 'Name'
    h3 = 'Price'
    h4 = 'Assets\nSuspect?'
    h5 = 'Rev.\nSuspect?'
    h6 = 'PPE\nSuspect?'
    h7 = 'ROE\nLow?'
    h8 = 'No\nDopeler\nBook\nValue?'

    h10 = 'Dopeler\nROE\n(Ave.)'
    h11 = 'Dopeler\nROE\n(Lowball)'
    h12 = 'Dopeler\nP/B'
    h13 = 'Dopeler\nPE'
    h14 = 'Dopeler\nYield'
    h15 = 'Dopeler\nBook\nValue'
    h16 = 'Dopeler\nEPS'
    h17 = 'Net\nLiquidity/Share'
    h18 = 'Sector'
    h19 = 'Industry'
    h20 = 'Assets\n(billions,\nSmartMoney)'
    h21 = 'Assets\n(billions,\nYahoo)'
    h22 = 'Assets\nRatio\n(dB)'
    h23 = 'Revenue\n(billions,\nSmartMoney)'
    h24 = 'Revenue\n(billions,\nYahoo)'
    h25 = 'Revenue\nRatio\n(dB)'
    h26 = 'PPE\nGrowth\n(dB)'
    h27 = 'PPE\nGrowth\nStd.\nDev\n(dB)'
    h28 = 'Dopeler\nROE\n(rel.\nstd.\ndev.)'
    h29 = 'Dopeler\nROE (Y1)'
    h30 = 'Dopeler\nROE (Y2)'
    h31 = 'Dopeler\nROE (Y3)'
    h32 = 'Dopeler\nROE (Y4)'

    resultswriter.writerow ([h1, h2, h3, h4, h5, h6, h7, h8, h10, h11, h12, h13, h14, h15, h16, h17, h18, h19, h20, h21, h22, h23, h24, h25, h26, h27, h28, h29, h30, h31, h32])
    while i_stock <= i_stock_max:
        c1 = list_symbol [i_stock]
        c2 = list_name [i_stock]
        c3 = str (list_price [i_stock])
        c4 = str (list_assets_suspect [i_stock])
        c5 = str (list_rev_suspect [i_stock])
        c6 = str (list_ppe_suspect [i_stock])
        c7 = str (list_roe_low [i_stock])
        c8 = str (list_iv_none [i_stock])

        c10 = dec_thou (list_roe_ave [i_stock])
        c11 = dec_thou (list_roe_lowball [i_stock])
        c12 = dec_hund (list_pb [i_stock])
        c13 = dec_tenth (list_pe [i_stock])
        c14 = dec_thou (list_yield [i_stock])
        c15 = dec_hund (list_intrinsic_ps [i_stock])
        c16 = dec_thou (list_eps [i_stock])
        c17 = dec_hund ( list_netliq_ps [i_stock])
        c18 = list_sector [i_stock]
        c19 = list_industry [i_stock]

        c20 = str (list_assets_smartmoney [i_stock])
        c21 = str (list_assets_yahoo [i_stock])
        c22 = dec_thou (list_assets_ratio [i_stock])
        c23 = str (list_rev_smartmoney [i_stock])
        c24 = str (list_rev_yahoo [i_stock])
        c25 = dec_thou (list_rev_ratio [i_stock])
        c26 = dec_thou (list_ppe_growth [i_stock])
        c27 = dec_thou (list_ppe_growth_dev [i_stock])
        c28 = dec_thou (list_roe_dev [i_stock])
        c29 = dec_thou (list_roe0 [i_stock])
        c30 = dec_thou (list_roe1 [i_stock])
        c31 = dec_thou (list_roe2 [i_stock])
        c32 = dec_thou (list_roe3 [i_stock])
        
        resultswriter.writerow([c1, c2, c3, c4, c5, c6, c7, c8, c10, c11, c12, c13, c14, c15, c16, c17, c18, c19, c20, c21, c22, c23, c24, c25, c26, c27, c28, c29, c30, c31, c32])
        i_stock = i_stock + 1
    
####################################################
# PART 8: PRINT THE RESULTS (FILTERED) TO A CSV FILE
####################################################

i_stock = 0
i_stock_max = len (list_symbol) -1
filename_output = dir_output + "/results.csv"

with open(filename_output, 'w') as csvfile:
    resultswriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    h1 = 'Symbol'
    h2 = 'Name'
    h3 = 'Price'
    h4 = 'Dopeler\nP/B'
    h5 = 'Dopeler\nROE\n(Ave.)'
    h6 = 'Dopeler\nROE\n(Lowball)'
    h7 = 'Dopeler\nPE'
    h8 = 'Dopeler\nYield'
    h10 = 'Dopeler\nBook\nValue'
    h11 = 'Dopeler\nEPS'
    h12 = 'Net\nLiquidity/Share'
    h13 = 'Sector'
    h14 = 'Industry'
    h15 = 'Assets\nDiff.\n(dB)'
    h16 = 'Rev.\nDiff\n(dB)'
    h17 = 'PPE\nGrowth\nDev.\n(dB)'

    resultswriter.writerow ([h1, h2, h3, h4, h5, h6, h7, h8, h10, h11, h12, h13, h14, h15, h16, h17])
    while i_stock <= i_stock_max:
        roe_ave = list_roe_ave [i_stock] # Dopeler ROE
        pb = list_pb [i_stock] # Dopeler Price/Book
        pe = list_pe [i_stock] # Dopeler PE
        yld = list_yield [i_stock] # Dopeler yield
        bv = list_intrinsic_ps [i_stock] # Dopeler Book Value (estimated intrinsic value)
        eps = list_eps [i_stock] # Dopeler Earnings Per Share
        netliq = list_netliq_ps [i_stock] # Net liquidity per share

        cond1 = list_assets_suspect [i_stock]
        cond2 = list_rev_suspect [i_stock]
        cond3 = list_ppe_suspect [i_stock]
        cond4 = list_roe_low [i_stock]
        cond5 = list_iv_none [i_stock]
        to_print = not (cond1 or cond2 or cond3 or cond4 or cond5)

        if to_print == True:
            c1 = list_symbol [i_stock]
            c2 = list_name [i_stock]
            c3 = str (list_price [i_stock])
            c4 = dec_hund (list_pb [i_stock])
            c5 = dec_thou (list_roe_ave [i_stock])
            c6 = dec_thou (list_roe_lowball [i_stock])
            c7 = dec_tenth (list_pe [i_stock])
            c8 = dec_thou (list_yield [i_stock])
            c10 = dec_hund (list_intrinsic_ps [i_stock])
            c11 = dec_thou (list_eps [i_stock])
            c12 = dec_hund( list_netliq_ps [i_stock])
            c13 = list_sector [i_stock]
            c14 = list_industry [i_stock]
            c15 = dec_thou (list_assets_ratio [i_stock])
            c16 = dec_thou (list_rev_ratio [i_stock])
            c17 = dec_thou (list_ppe_growth_dev [i_stock])
        
            resultswriter.writerow([c1, c2, c3, c4, c5, c6, c7, c8, c10, c11, c12, c13, c14, c15, c16, c17])
        i_stock = i_stock + 1

###############################################
# PART 9: COPY THE CSV FILES TO THE DRUPAL SITE
###############################################
# dir_home = '/home/doppler' # Home directory on server
# dir_output = dir_screen + '/screen-output' 
src = dir_output + '/*'
dest = dir_home + '/webapps/drup/sites/default/files/screen-results'
if (is_server):
    print "Copying results to the Drupal web site"
    os.system ('cp ' + src + ' ' + dest)
