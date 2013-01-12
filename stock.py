#! /usr/bin/python

import pwd
import sys
import os
import datetime
import time, random
import urllib
import urllib2
import csv
import glob
import re
import math
import operator

##########################################################################################
# PART 1: FIGURE OUT THE DIRECTORY STRUCTURE
# THIS IS NEEDED TO DISTINGUISH BETWEEN THE DEVELOPMENT ENVIRONMENT AND SERVER ENVIRONMENT
# THIS DETERMINES THE PATH TO CRITICAL DIRECTORIES AND FILES
##########################################################################################

# Assume that this is the server environment
dir_home = '/home/doppler' # Home directory on server
dir_main = dir_home + '/webapps/scripts_doppler/dopplervalueinvesting'

# Check this assumption
is_server = os.path.exists(dir_home) # Determine if this is the server environment

# Adjustments to make if this is the development environment instead of the server environment
if not (is_server):
    # Get your username (not root)
    uname=pwd.getpwuid(1000)[0]
    dir_home = '/home/' + uname
    dir_main = dir_home + '/dopplervalueinvesting'

# Determine the paths of critical directories
dir_input_screen = dir_main + '/screen-input'
dir_input_stock = dir_main + '/stock-input'
dir_output_stock = dir_main + '/stock-output'  

######################################################################################
# PART 2: DOWNLOAD THE LISTS OF AMEX, NYSE, AND NASDAQ STOCKS FROM THE NASDAQ WEB SITE
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

URL_BASE_NASDAQ = 'http://www.nasdaq.com/screening/companies-by-industry.aspx?exchange='
URL_END_NASDAQ = '&render=download'

url1 = URL_BASE_NASDAQ + 'AMEX' + URL_END_NASDAQ
url2 = URL_BASE_NASDAQ + 'NYSE' + URL_END_NASDAQ
url3 = URL_BASE_NASDAQ + 'NASDAQ' + URL_END_NASDAQ

file1 = dir_input_screen + '/companylist-amex.csv'
file2 = dir_input_screen + '/companylist-nyse.csv'
file3 = dir_input_screen + '/companylist-nasdaq.csv'
file_age_max_hours = 12

print ('Downloading list of AMEX stocks')
download_page (url1, file1, file_age_max_hours)
print ('Downloading list of NYSE stocks')
download_page (url2, file2, file_age_max_hours)
print ('Downloading list of NASDAQ stocks')
download_page (url3, file3, file_age_max_hours)

##############################################################################################
# PART 3: For a given exchange, obtain a list of ticker symbols for stocks that are NOT funds.
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
        file_stock = CSVfile (dir_input_screen + '/companylist-' + self.exch_abbrev + '.csv')
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
# PART 4: Using Exchange.symbol_selected, compile the list of ticker symbols from the AMEX, NYSE, and NASDAQ exchanges.
#######################################################################################################################
print "******************************"
print "BEGIN acquiring list of stocks"

Exchange1 = Exchange ('amex')
Exchange2 = Exchange ('nasdaq')
Exchange3 = Exchange ('nyse')

list_symbol = Exchange1.symbol_selected () + Exchange2.symbol_selected () + Exchange3.symbol_selected ()
list_name = Exchange1.name_selected () + Exchange2.name_selected () + Exchange3.name_selected ()
list_price = Exchange1.price_selected () + Exchange2.price_selected () + Exchange3.price_selected ()
list_nshares = Exchange1.nshares_selected () + Exchange2.nshares_selected () + Exchange3.nshares_selected ()
list_sector = Exchange1.sector_selected () + Exchange2.sector_selected () + Exchange3.sector_selected ()
list_industry = Exchange1.industry_selected () + Exchange2.industry_selected () + Exchange3.industry_selected ()

num_stocks = len (list_symbol)
print "Total number of stocks: " + str(num_stocks)
print "FINISHED acquiring list of stocks"
print "*********************************"

#########################################################
# PART 5: GET LIST OF STOCKS TO ANALYZE IN GREATER DETAIL
#########################################################

list_path_all = glob.glob(dir_input_stock + '/*.csv')
i_path = 0
i_path_max = len (list_path_all) -1
list_path_selected = []
list_symbol_selected = []
while i_path <= i_path_max:
    pathname = list_path_all [i_path]
    filename = pathname
    filename = filename.replace (dir_input_stock, '')
    filename = filename [1:]
    if filename <> "codes.csv":
        symbol = filename.replace ('.csv', '')
        symbol = symbol.upper()
        list_path_selected.append (pathname)
        list_symbol_selected.append (symbol)
    i_path = i_path + 1

#####################################################################
# PART 6: GET NAMES AND PRICES OF STOCKS TO ANALYZE IN GREATER DETAIL
#####################################################################

# Get index number of stock symbol (string) in 1-D list
# Inputs: string, 1-D list
# Output: integer
def get_index (str_input, list_input):
    index_output = -1
    i_item = 0
    i_item_max = len (list_input) -1
    while i_item <= i_item_max:
        item_current = list_input [i_item]
        if item_current == str_input:
            index_output = i_item
        i_item = i_item + 1
    if index_output < 0:
        index_output = None
    return index_output

i = 0
i_max = len (list_symbol_selected) -1
list_symbol_found = []
list_path_found = []
list_name_found = []
list_price_found = []
while i <= i_max:
    path = list_path_selected [i]
    symbol = list_symbol_selected [i]
    i_symbol = get_index (symbol, list_symbol)
    if i_symbol <> None:
        name = list_name [i_symbol]
        price = list_price [i_symbol]
        list_symbol_found.append (symbol)
        list_path_found.append (path)
        list_name_found.append (name)
        list_price_found.append (price)
    i = i + 1

##########################
# PART 7: DEFINE FUNCTIONS
##########################

# Purpose: extract a given column from a 2-D list
# Input: 2-D data list
# Output: 1-D data list representing the (n_local+1) -th column of the input list
def column (list_local, n_local):
    list_transpose = zip (*list_local)
    return list_transpose [n_local]

# Purpose: extract a given column from a 2-D list but omit the top row
# Input: 2-D data list
# Output: 1-D data list representing the (n_local+1) -th column of the input list, minus the first entry
def column_data (list_local, n_local):
    list1 = column (list_local, n_local)
    list2 = list1 [1:]
    return list2

# Purpose: count the number of columns in a 2-D list
# Input: 2-D data list
# Output: integer representing the number of columns of the 2-D list
def num_of_columns (list_local):
    list_transpose = zip (*list_local)
    n_local = len (list_transpose)
    return n_local

# Cuts off the first two entries of a list and then reverses it
# Used to process the financial numbers in the stock data
# The first column is the line item.  The second column is the code.
# The numbers to process are in the rest of the data.
# Input: 2-D data list
# Output: 1-D data list representing the (n_local+1) -th row of the input list
def row_rev (list_local, n_local):
    list1 = list_local [n_local] # (n_local+1) -th row
    list2 = list1 [2:]
    list3 = list2 [::-1] # reverses list
    return list3
    
# Converts a row of strings into floating point numbers
# Input: 1-D list of strings
# Output: 1-D list of floating point numbers
def string_to_float (list_local):
    list1 = []
    for item in list_local:
        item1 = item
        item2 = item1.replace (',', '')
        try:
            item3 = float (item2)
        except:
            item3 = None
        list1.append (item3)
    return list1
    
# Converts a row of strings into integers
# Input: 1-D list of strings
# Output: 1-D list of floating point numbers
def string_to_int (list_local):
    list1 = []
    for item in list_local:
        item1 = item
        item2 = item1.replace (',', '')
        try:
            item3 = int (item2)
        except:
            item3 = None
        list1.append (item3)
    return list1
    
# Finds the average in a list of numbers
# Input: 1-D list of floating point numbers
# Output: floating point number
def mean (list_local):
    try:
        total = float (sum (list_local))
        n = len (list_local)
        x = float (total/n)
    except:
        x = None
    return x

# Finds the n_local-element moving average in a list of numbers
# Input: 1-D list of floating point numbers
# Output: 1-D list of floating point numbers
def moving_average (list_local, n_local):
    list1 = list_local
    list2 = []
    n_cols = len (list1)
    c_min = 0
    c_max = n_cols - 1
    c = c_min
    x_min = 0
    x_max = n_local - 1
    while c <= c_max:
        list3 = []
        x = x_min
        while x <= x_max:
            if c - x < 0:
                element = None
            else:
                element = list1 [c - x]
            list3.append (element)
            x = x + 1
        ave_moving = mean (list3)
        list2.append (ave_moving)
        c = c + 1
    return list2
    
# Changes the "None" elements in a list to zeros
# Input: 1-D list
# Output: 1-D list
def none_to_zero (list_input):
    list1 = list_input
    list2 = []
    for item in list1:
        if item == None:
            list2.append (0.0)
        else:
            list2.append (item)
    return list2
        
# Combine two 1-D lists of equal length into two lists
# This is needed for convertible debt.
# The first row of data is based on the assumption that convertibles remain as debt.
# The second row is based on the assumption that convertibles become shares.
# In the end, we will use the assumption that produces the LOWER estimate of intrinsic value.
def combine2lists (list1, list2):
    list3 = []
    list3.append (list1)
    list3.append (list2)
    return list3


# Inputs: 2-D list consisting of two 1-D lists of equal length
# and a 1-D list used for selecting from the two lists
# Output: 1-D list
def select_option_conv (list1, list2):
    # list1 [0]: consists of the list of values assuming convertibles = debt
    # list1 [1]: consists of the list of values assuming convertibles = shares
    # list2: selects 0 or 1
    # list3: output
    list3 = []
    n_cols = len (list2)
    c_min = 0
    c_max = n_cols - 1
    c = c_min
    while c<=c_max:
        try:
            element = list1 [list2 [c]] [c]
        except:
            element = None
        list3.append (element)
        c = c + 1
    return list3

#############################################
# PART 8: DEFINE THE CLASS CSVFILE (pathname)
#############################################
            	
# This defines the class CSVfile (pathname).
# Input: string (name of csv file)
# Output: 2-D list fed by the input file
class CSVfile:
    def __init__ (self, pathname):
        self.pathname = pathname

    def filelist (self):
        locallist = []
        with open (self.pathname, 'rb') as f:
            reader = csv.reader (f, delimiter = ',', quotechar = '"', quoting = csv.QUOTE_MINIMAL)
            for row in reader:
                locallist.append (row)
        return locallist

#######################################################################
# PART 9: DEFINE THE CLASS STOCK (symbol, path, name, price, n_smooth)
# n_smooth: number of years to average when calculating the Doppler ROE
#######################################################################

# This defines the class Stock (symbol)
# Input: stock symbol
# Outputs: 2-D data list fed by the input file and 1-D data lists
class Stock:
    def __init__ (self, symbol, path, name, price, n_smooth):
        self.symbol = symbol
        self.path = path
        self.name = name
        self.price = price
        self.n_smooth = n_smooth
    
    # Purpose: reads the contents of the financial data file into a 2-D list
    # Input: stock file
    # Output: 2-D data list
    def data (self):
        file_stock = CSVfile (path)
        list_stock = file_stock.filelist ()
        return list_stock
        
    # Purpose: extracts the title of each line item into a 1-D list
    # Input: 2-D data list from data function
    # Output: 1-D list of integers (first column, excluding the top row)
    def lineitem_titles (self):
        list1 = self.data ()
        list2 = column_data (list1, 0) # Excludes the top row of the stock data file
        list3 = list2 [2:] # Excludes the next 2 rows of the stock data file
        return list3

    # Purpose: extracts the specific category, general category, and sign (+/-) for each line item
    # Input: 2-D list from data function
    # Output: 2-D list (3 columns)
    # First column: specific codes
    # Second column: general codes
    # Third column: signs, +1 or -1
    def lineitem_codes (self):
        list1 = self.data ()
        spec_local = column_data (list1, 1) # First column of stock data, excludes the top row
        finallist = []
        file_codes = CSVfile (dir_input_stock + '/codes.csv')
        list_codefile = file_codes.filelist ()
        spec_codefile = column_data (list_codefile, 1)
        gen_codefile = column_data (list_codefile, 3)
        signs_codefile = column_data (list_codefile, 2)
        local_spec_lineitems = spec_local
        local_gen_lineitems = []
        local_signs_lineitems = []
        for item in local_spec_lineitems: # Go through the specific codes in the stock data
            try:
                i_spec = spec_codefile.index (item)
                local_gen_lineitems.append (gen_codefile [i_spec])
                local_signs_lineitems.append (signs_codefile [i_spec])
            except:
				local_gen_lineitems.append ('N/A')
				local_signs_lineitems.append ('0')
        finallist = zip (local_spec_lineitems, local_signs_lineitems, local_gen_lineitems)
        finallist = zip (finallist)
        return finallist

    # Purpose: obtain the specific category for each line item
    # Input: 2-D list of strings and integers from lineitem_codes
    # Output: 1-D list
    def lineitem_spec (self):
        list1 = self.lineitem_codes () # Excludes the top row
        locallist = column_data (column_data (list1, 0), 0) # Excludes the next two rows
        return locallist
    
    # Purpose: obtain the +/- sign for each line item
    # Input: 2-D list of strings and integers from lineitem_codes
    # Output: 1-D array of numbers
    def lineitem_signs (self):
        list1 = self.lineitem_codes () # Excludes the top row
        list2 = column_data (column_data (list1, 0), 1) # Excludes the next two rows
        list3 = string_to_int (list2)
        return list3
        
    # Purpose: obtain the general category for each line item
    # Input: 2-D list of strings and integers from lineitem_codes
    # Output: 1-D list    
    def lineitem_gen (self):
        list1 = self.lineitem_codes () # Excludes the top row
        locallist = column_data (column_data (list1, 0), 2) # Excludes the next two rows
        return locallist
        
    # Purpose: extract the list of years
    # Input: 2-D data list from data function
    # Output: 1-D list (top row, excluding the first two columns)
    # Note also the reversal, which puts the most recent year last in the sequence
    def years (self):
        list1 = self.data ()
        list2 = row_rev (list1, 0) # Removes the first two columns, then reverses
        return list2
    
    # Creates a list of zeros
    # Input: years list
    # Output: list of zeros with the same length as the years list
    def list_zero (self):
        list1 = self.years ()
        list2 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            list2.append (0.0)
            c = c + 1
        return list2

    # Creates a list of None
    # Input: years list
    # Output: list of None with the same length as the years list
    def list_none (self):
        list1 = self.years ()
        list2 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            list2.append (None)
            c = c + 1
        return list2    
    
    # Purpose: extract the split factor for each year
    # Input: 2-D data list from data function
    # Output: 1-D array of numbers (2nd row, excluding the first two columns)
    # Note also the reversal, which puts the most recent year last in the sequence
    def split_f (self):
        list1 = self.data ()
        list2 = row_rev (list1, 1) # Removes the first two columns, then reverses
        list3 = string_to_float (list2)
        return list3
        
    # Purpose: extract the split factor for each year
    # Input: 2-D data list from data function
    # Output: 1-D list of numbers (3rd row, excluding the first two columns)
    # Note also the reversal, which puts the most recent year last in the sequence
    def unit_plus(self):
        list1 = self.data ()
        list2 = row_rev (list1, 2) # Removes the first two columns, then reverses
        list3 = string_to_float (list2)
        return list3
                
    # Purpose: extract the split factor for each year
    # Input: 2-D data list from data function
    # Output: 1-D list of numbers (4th row, excluding the first two columns) OR
    # a 1-D list of zeros
    # Note also the reversal, which puts the most recent year last in the sequence
    def unit_minus (self):
        list1 = self.data ()
        list2 = row_rev (list1, 3) # Removes the first two columns, then reverses
        if list1 [3][1] == 'un-':
            list3 = string_to_float (list2)
        else:
            list3 = [0 for i in list2]
        return list3

    # Purpose: obtain the number of line items
    # Input: 1-D data list from lineitem_figures function
    # Output: integer (number of rows in lineitem_figures)
    def num_lineitems (self):
		list1 = self.lineitem_spec ()
		local_num = len (list1)
		return local_num
	
	# Purpose: obtain the number of years of data
	# Input: 1-D data list from years function
    # Output: integer (number of rows in lineitem_figures)
    def num_years (self):
		list1 = self.years ()
		local_num = len (list1)
		return local_num

    # Purpose: obtain the financial figures in numbers to be used for computation
    # Input: 2-D data list from data function
    # Output: 2-D list of numbers (excluding the top row and first two columns)
    # Note also the reversal, which puts the most recent year last in the sequence
    # Note that the strings are transformed into floating point numbers
    def lineitem_figures (self):
        list1 = self.data ()
        # Row number = r + 1
		# First row: r = 0
		# Last row: r = total number of rows - 1
        r_max_data = len (list1) -1
        r_min_data = 3 # top row = year, 2nd row = split factor, 3rd row = unit (plus)
        list2 = []
        r = r_min_data
        while r <= r_max_data:
            line1 = row_rev(list1, r) # Reverses, cuts off first two columns
            list2.append (line1)
            r = r + 1
        # list2 = data minus first two columns and first three rows
        list3 = []
        for line in list2:
            line1 = line
            line2 = string_to_float (line1)
            list3.append (line2)
        # list3 = list2 converted to floating point numbers
        return list3
        
    # Obtain the list of line items for a given combination of general category and sign
    # Input: 1-D data lists from lineitem_gen function and lineitem_signs
    # Output: 1-D list of line numbers
    def lineitem_index (self, gen_seek, sign_seek):
        list1 = self.lineitem_gen ()
        list2 = self.lineitem_signs ()
        list3 = []
        # Row number = r + 1
		# First row: r = 0
		# Last row: r = total number of rows - 1
        r_max_data = len (list1) -1
        r_min_data = 0
        r = r_min_data
        while r <= r_max_data:
            if list1 [r] == gen_seek:
                if list2 [r] == sign_seek:
					list3.append (r)
            r = r + 1
        return list3
        
    # Obtain the list of titles for the line items of a given general category and sign
    # Inputs: 1-D lists
    # Output: 1-D list
    def lineitem_cat_titles (self, gen_seek, sign_seek):
        list1 = self.lineitem_index (gen_seek, sign_seek)
        list2 = self.lineitem_titles ()
        list3 = []
        for item in list1:
            list3.append (list2 [item])
        return list3

    # Obtain the list of specific categories for the line items of a given general category and sign
    # Inputs: 1-D lists
    # Output: 1-D list	
    def lineitem_cat_spec (self, gen_seek, sign_seek):
        list1 = self.lineitem_index (gen_seek, sign_seek)
        list2 = self.lineitem_spec ()
        list3 = []
        for item in list1:
            list3.append (list2 [item])
        return list3
        
    # Obtain the figures for the line items of a given general category and sign
    # Inputs: 1-D lists
    # Output: 2-D list
    def lineitem_cat_figures (self, gen_seek, sign_seek):
        list1 = self.lineitem_index (gen_seek, sign_seek)
        list2 = self.lineitem_figures ()
        list3 = []
        for item in list1:
            list3.append (list2 [item])
        return list3
    
    # Obtain the total figures for a given general category and sign
    # NOTE: These figures are in NOMINAL units, not dollars.
    # Inputs: 1-D lists, 2-D list
    # Output: 1-D list
    # Obtain the total figures for a given general category and sign
    # NOTE: These figures are in NOMINAL units, not dollars.
    # Inputs: 1-D lists, 2-D list
    # Output: 1-D list
    def lineitem_cat_total (self, gen_seek, sign_seek):
        list1 = self.lineitem_cat_figures (gen_seek, sign_seek)
        list2 = []
        n_rows = len (list1)
        n_cols = num_of_columns (list1)
        r_min = 0
        r_max = n_rows - 1
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            local_total = 0.0
            r = r_min
            while r <= r_max:
                try:
                    local_total = local_total + list1 [r][c]
                except:
                    local_total = None
                r = r + 1
            list2.append (local_total)
            c = c + 1
        if list2 ==[]:
            list2 = self.list_none ()
        return list2
          
    def liqplus_titles (self):
        list1 = self.lineitem_cat_titles ('liq', 1)
        return list1
        
    def liqplus_spec (self):
        list1 = self.lineitem_cat_spec ('liq', 1)
        return list1
    
    def liqplus (self):
        list1 = self.lineitem_cat_total ('liq', 1)
        return list1
    
    def liqminus_titles (self):
        list1 = self.lineitem_cat_titles ('liq', -1)
        return list1
        
    def liqminus_spec (self):
        list1 = self.lineitem_cat_spec ('liq', -1)
        return list1
    
    def liqminus (self):
        list1 = self.lineitem_cat_total ('liq', -1)
        return list1

    # Liquid assets ($)
    def dollars_liq (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_liqplus = self.liqplus ()
        list_liqminus = self.liqminus ()
        list1 = []
        n_cols = len (list_liqplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_liqplus [c] - list_unminus [c] * list_liqminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_liqplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

    def assetplus_spec (self):
        list1 = self.lineitem_cat_spec ('asset', 1)
        return list1

    def assetminus_spec (self):
        list1 = self.lineitem_cat_spec ('asset', -1)
        return list1

    def assetplus (self):
        list1 = self.lineitem_cat_total ('asset', 1)
        return list1

    def assetminus (self):
        list1 = self.lineitem_cat_total ('asset', -1)
        return list1

    # Total assets ($)
    def dollars_asset (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_assetplus = self.assetplus ()
        list_assetminus = self.assetminus ()
        list1 = []
        n_cols = len (list_assetplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_assetplus [c] - list_unminus [c] * list_assetminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_assetplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

    def equityplus_spec (self):
        list1 = self.lineitem_cat_spec ('equity', 1)
        return list1

    def equityminus_spec (self):
        list1 = self.lineitem_cat_spec ('equity', 1)
        return list1

    def equityplus (self):
        list1 = self.lineitem_cat_total ('equity', 1)
        return list1

    def equityminus (self):
        list1 = self.lineitem_cat_total ('equity', -1)
        return list1    

    # Total equity ($)
    def dollars_equity (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_equityplus = self.equityplus ()
        list_equityminus = self.equityminus ()
        list1 = []
        n_cols = len (list_equityplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_equityplus [c] - list_unminus [c] * list_equityminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_equityplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

        
    def liabplus_titles (self):
        list1 = self.lineitem_cat_titles ('liab', 1)
        return list1
        
    def liabplus_spec (self):
        list1 = self.lineitem_cat_spec ('liab', 1)
        return list1
    
    def liabplus (self):
        list1 = self.lineitem_cat_total ('liab', 1)
        return list1
    
    def liabminus_titles (self):
        list1 = self.lineitem_cat_titles ('liab', -1)
        return list1
        
    def liabminus_spec (self):
        list1 = self.lineitem_cat_spec ('liab', -1)
        return list1
    
    def liabminus (self):
        list1 = self.lineitem_cat_total ('liab', -1)
        return list1
        
    # Nonconvertible liabilities only, assume convertibles become shares ($)        
    def dollars_liab_cshares (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.liabplus ()
        list_quantminus = self.liabminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = 0
            list1.append (dollars)
            c = c + 1
        return list1
        
    # Net liquid assets, convertibles as shares ($)
    def dollars_netliq_cshares (self):
        list_liq = self.dollars_liq ()
        list_asset = self.dollars_asset ()
        list_equity = self.dollars_equity ()
        list_liab = self.dollars_liab_cshares ()
        list1 = []
        n_cols = len (list_liq)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_liq [c] - (list_asset [c] - list_equity [c] ) - list_liab [c]
            except:
                try:
                    dollars = list_liq [c] - (list_asset [c] - list_equity [c] )
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

    def liabc_titles (self):
        list1 = self.lineitem_cat_titles ('liabc', 1)
        return list1
        
    def liabc_spec (self):
        list1 = self.lineitem_cat_spec ('liabc', 1)
        return list1
    
    def liabc (self):
        list1 = self.lineitem_cat_total ('liabc', 1)
        list2 = none_to_zero (list1)
        return list2
    
    # Convertible liabilities ($)
    def dollars_liab_conv (self):
        list_quantplus = self.liabc ()
        list_unplus = self.unit_plus ()
        list1 = []
        n_cols = len (list_unplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c]
            except:
                dollars = 0    
            list1.append (dollars)
            c = c + 1
        return list1
        
    # Net liquidity, convertibles as debt ($)
    def dollars_netliq_cdebt (self):
        list_netliq = self.dollars_netliq_cshares ()
        list_asset = self.dollars_asset ()
        list_equity = self.dollars_equity ()
        list_liabc = self.dollars_liab_conv ()
        list1 = []
        n_cols = len (list_netliq)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_netliq [c] - list_liabc [c]
            except:
                try:
                    dollars = list_netliq [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1
     
    # Net liquidity
    # Row 1: Assume convertibles remain as debt.
    # Row 2: Assume convertibles are converted into shares.
    def dollars_netliq_2d (self):
		list1 = self.dollars_netliq_cdebt ()
		list2 = self.dollars_netliq_cshares ()
		list3 = combine2lists (list1, list2)
		return list3
                
    def shares_titles (self):
        list1 = self.lineitem_cat_titles ('shares', 1)
        return list1
        
    def shares_spec (self):
        list1 = self.lineitem_cat_spec ('shares', 1)
        return list1
    
    # Nonconvertible shares, total # of shares if none are converted
    def shares_cdebt (self):
        list1 = self.lineitem_cat_total ('shares', 1)
        return list1

    def shares_conv_titles (self):
        list1 = self.lineitem_cat_titles ('sharesc', 1)
        return list1
        
    def shares_conv_spec (self):
        list1 = self.lineitem_cat_spec ('sharesc', 1)
        return list1
        
    # Convertible shares, 0 if not listed
    def shares_conv (self):
        list1 = self.lineitem_cat_total ('sharesc', 1)
        list2 = none_to_zero (list1)
        return list2
        
    # Total shares, split adjusted, convertibles as debt
    def shares_adj_cdebt (self):
        list1 = self.shares_cdebt ()
        list2 = self.split_f ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                local_shares = list1 [c] * list2 [c]
            except:
                local_shares = None
            list3.append (local_shares)
            c = c + 1
        return list3
        
    # Total shares, split adjusted, convertibles as shares
    def shares_adj_cshares (self):
        list1 = self.shares_cdebt ()
        list2 = self.shares_conv ()
        list3 = self.split_f ()
        list4 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                local_shares = (list1 [c] + list2 [c]) * list3 [c]
            except:
                local_shares = None
            list4.append (local_shares)
            c = c + 1
        return list4
        
    def shares_adj_2d (self):
        list1 = self.shares_adj_cdebt ()
        list2 = self.shares_adj_cshares ()
        list3 = []
        list3.append (list1)
        list3.append (list2)
        return list3
		
    def ppecplus_titles (self):
        list1 = self.lineitem_cat_titles ('ppec', 1)
        return list1
        
    def ppecplus_spec (self):
        list1 = self.lineitem_cat_spec ('ppec', 1)
        return list1
    
    def ppecplus (self):
        list1 = self.lineitem_cat_total ('ppec', 1)
        return list1
    
    def ppecminus_titles (self):
        list1 = self.lineitem_cat_titles ('ppec', -1)
        return list1
        
    def ppecminus_spec (self):
        list1 = self.lineitem_cat_spec ('ppec', -1)
        return list1
    
    def ppecminus (self):
        list1 = self.lineitem_cat_total ('ppec', -1)
        return list1

    # Plant/property/equipment capital ($)
    def dollars_ppec (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.ppecplus ()
        list_quantminus = self.ppecminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1
        
    def cfoplus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_P', 1)
        return list1
        
    def cfoplus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_P', 1)
        return list1
    
    def cfoplus (self):
        list1 = self.lineitem_cat_total ('CF_P', 1)
        return list1
    
    def cfominus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_P', -1)
        return list1
        
    def cfominus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_P', -1)
        return list1
    
    def cfominus (self):
        list1 = self.lineitem_cat_total ('CF_P', -1)
        return list1
        
    # Cash flow from operations ($)
    def dollars_cfo (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cfoplus ()
        list_quantminus = self.cfominus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

    def cftax_titles (self):
        list1 = self.lineitem_cat_titles ('CF_N2T', 1)
        return list1
        
    def cftax_spec (self):
        list1 = self.lineitem_cat_spec ('CF_N2T', 1)
        return list1
    
    def cftaxplus (self):
        list1 = self.lineitem_cat_total ('CF_N2T', 1)
        return list1
    
    def cftaxminus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_N2T', -1)
        return list1
        
    def cftaxminus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_N2T', -1)
        return list1
    
    def cftaxminus (self):
        list1 = self.lineitem_cat_total ('CF_N2T', -1)
        return list1
        
    # Income tax expense ($)
    def dollars_cftax (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cftaxplus ()
        list_quantminus = self.cftaxminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

    def cfn2f_titles (self):
        list1 = self.lineitem_cat_titles ('CF_N2F', 1)
        return list1
        
    def cfn2f_spec (self):
        list1 = self.lineitem_cat_spec ('CF_N2F', 1)
        return list1
    
    def cfn2fplus (self):
        list1 = self.lineitem_cat_total ('CF_N2F', 1)
        return list1
    
    def cfn2fminus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_N2F', -1)
        return list1
        
    def cfn2fminus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_N2F', -1)
        return list1
    
    def cfn2fminus (self):
        list1 = self.lineitem_cat_total ('CF_N2F', -1)
        return list1
        
    # Interest expense, negative operating cash flows reclassified as finance ($)
    def dollars_cfn2f (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cfn2fplus ()
        list_quantminus = self.cfn2fminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = 0
            list1.append (dollars)
            c = c + 1
        return list1

    def cfp2f_titles (self):
        list1 = self.lineitem_cat_titles ('CF_P2F', 1)
        return list1
        
    def cfp2f_spec (self):
        list1 = self.lineitem_cat_spec ('CF_P2F', 1)
        return list1
    
    def cfp2fplus (self):
        list1 = self.lineitem_cat_total ('CF_P2F', 1)
        return list1
    
    def cfp2fminus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_P2F', -1)
        return list1
        
    def cfp2fminus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_P2F', -1)
        return list1
    
    def cfp2fminus (self):
        list1 = self.lineitem_cat_total ('CF_P2F', -1)
        return list1
        
    # Interest income and cash flow adjustments for changes in current liabilities
    # Positive operating cash flow reclassified as finance ($)
    def dollars_cfp2f (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cfp2fplus ()
        list_quantminus = self.cfp2fminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = None
            list1.append (dollars)
            c = c + 1
        return list1

    def cfp2i_titles (self):
        list1 = self.lineitem_cat_titles ('CF_P2I', 1)
        return list1
        
    def cfp2i_spec (self):
        list1 = self.lineitem_cat_spec ('CF_P2I', 1)
        return list1
    
    def cfp2iplus (self):
        list1 = self.lineitem_cat_total ('CF_P2I', 1)
        return list1
    
    def cfp2iminus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_P2I', -1)
        return list1
        
    def cfp2iminus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_P2I', -1)
        return list1
    
    def cfp2iminus (self):
        list1 = self.lineitem_cat_total ('CF_P2I', -1)
        return list1
        
    # Gains classified as operating and not offset
    # Positive operating cash flow reclassified as investing ($)
    def dollars_cfp2i (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cfp2iplus ()
        list_quantminus = self.cfp2iminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = 0
            list1.append (dollars)
            c = c + 1
        return list1

    def cfn2i_titles (self):
        list1 = self.lineitem_cat_titles ('CF_N2I', 1)
        return list1
        
    def cfn2i_spec (self):
        list1 = self.lineitem_cat_spec ('CF_N2I', 1)
        return list1
    
    def cfn2iplus (self):
        list1 = self.lineitem_cat_total ('CF_N2I', 1)
        return list1
    
    def cfn2iminus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_N2I', -1)
        return list1
        
    def cfn2iminus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_N2I', -1)
        return list1
    
    def cfn2iminus (self):
        list1 = self.lineitem_cat_total ('CF_N2I', -1)
        return list1
        
    # Losses classified as operating and not offset
    # Negative operating cash flow reclassified as investing ($)
    def dollars_cfn2i (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cfn2iplus ()
        list_quantminus = self.cfn2iminus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = 0
            list1.append (dollars)
            c = c + 1
        return list1

    def cf2o_titles (self):
        list1 = self.lineitem_cat_titles ('CF_2O', 1)
        return list1
        
    def cf2o_spec (self):
        list1 = self.lineitem_cat_spec ('CF_2O', 1)
        return list1
    
    def cf2oplus (self):
        list1 = self.lineitem_cat_total ('CF_2O', 1)
        return list1
    
    def cf2ominus_titles (self):
        list1 = self.lineitem_cat_titles ('CF_2O', -1)
        return list1
        
    def cf2ominus_spec (self):
        list1 = self.lineitem_cat_spec ('CF_2O', -1)
        return list1
    
    def cf2ominus (self):
        list1 = self.lineitem_cat_total ('CF_2O', -1)
        return list1
        
    # Any investing or financing line items reclassified as operating ($)
    # NOTE: usually not present
    def dollars_cf2o (self):
        list_unplus  = self.unit_plus ()
        list_unminus = self.unit_minus ()
        list_quantplus = self.cf2oplus ()
        list_quantminus = self.cf2ominus ()
        list1 = []
        n_cols = len (list_quantplus)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list_unplus [c] * list_quantplus [c] - list_unminus [c] * list_quantminus [c]
            except:
                try:
                    dollars = list_unplus [c] * list_quantplus [c]
                except:
                    dollars = 0
            list1.append (dollars)
            c = c + 1
        return list1

    # Cash flow ($)
    def dollars_cf (self):
        list1p = self.dollars_cfo ()
        list2p = self.dollars_cftax ()
        list3p = self.dollars_cfn2f ()
        list1n = self.dollars_cfp2f ()
        list2n = self.dollars_cfp2i ()
        list4p = self.dollars_cfn2i ()
        list5p = self.dollars_cf2o ()
        list_output = []
        n_cols = len (list1p)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            dollars = 0
            try:
                dollars = list1p[c] + list2p[c] + list3p[c] + list4p[c] + list5p[c] - list1n[c] - list2n[c]
            except:
                dollars = None
            list_output.append (dollars)
            c = c + 1
        return list_output
 
    # Normalized capital spending ($)
    def dollars_cap (self):
        list1 = self.dollars_ppec ()
        list2 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c - 1 < 0:
                    dollars = None
                else:
                    dollars = .1 * list1 [c-1]
            except:
                dollars = None
            list2.append (dollars)
            c = c + 1
        return list2

    # Free cash flow, unsmoothed ($)
    def dollars_fcf (self):
        list1 = self.dollars_cf ()
        list2 = self.dollars_cap ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                dollars = list1 [c] - list2 [c]
            except:
                dollars = None
            list3.append (dollars)
            c = c + 1
        return list3

    # Doppler ROE, return on PPE
    # (free cash flow in year y divided by plant/property/equipment in year y-1)
    def return_ppe (self):
        list1 = self.dollars_fcf ()
        list2 = self.dollars_ppec ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c - 1 < 0:
                    dollars = None
                else:
                    dollars = list1[c] / list2[c-1]
            except:
                dollars = None
            list3.append (dollars)
            c = c + 1
        return list3

    # Net liquid assets, convertible = debt, $ per share
    def psh_netliq_cdebt (self):
        list1 = self.dollars_netliq_cdebt ()
        list2 = self.shares_adj_cdebt ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                psh = list1[c] / list2[c]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3

    # Net liquid assets, convertible = shares, $ per share
    def psh_netliq_cshares (self):
        list1 = self.dollars_netliq_cshares ()
        list2 = self.shares_adj_cshares ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                psh = list1[c] / list2[c]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3
        
    # Net liquid assets, convertible = debt, convertible = shares
    def psh_netliq_2d (self):
        list1 = self.psh_netliq_cdebt ()
        list2 = self.psh_netliq_cshares ()
        list3 = []
        list3.append (list1)
        list3.append (list2)
        return list3
    
    def psh_ppec_cdebt (self):
        list1 = self.dollars_ppec ()
        list2 = self.shares_adj_cdebt ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                psh = list1[c] / list2[c]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3
        
    def psh_ppec_cshares (self):
        list1 = self.dollars_ppec ()
        list2 = self.shares_adj_cshares ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                psh = list1[c] / list2[c]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3

    def psh_ppec_2d (self):
        list1 = self.psh_ppec_cdebt ()
        list2 = self.psh_ppec_cshares ()
        list3 = []
        list3.append (list1)
        list3.append (list2)
        return list3    
        
    def psh_ppec (self):
        list1 = self.psh_ppec_2d ()
        list2 = self.psh_select ()
        list3 = select_option_conv (list1, list2)
        return list3
    
    def return_ppe_ave (self):
        list1 = self.return_ppe ()
        n = n_smooth
        list2 = moving_average (list1, n)
        return list2
        
    def psh_fcf_smooth_cdebt (self):
        list1 = self.return_ppe_ave ()
        list2 = self.psh_ppec_cdebt ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c-1<0:
                    psh = None
                else:
                    psh = list1[c] * list2[c-1]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3
        
    def psh_fcf_smooth_cshares (self):
        list1 = self.return_ppe_ave ()
        list2 = self.psh_ppec_cshares ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c-1<0:
                    psh = None
                else:
                    psh = list1[c] * list2[c-1]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3

    def psh_fcf_smooth_2d (self):
        list1 = self.psh_fcf_smooth_cdebt ()
        list2 = self.psh_fcf_smooth_cshares ()
        list3 = []
        list3.append (list1)
        list3.append (list2)
        return list3

    
    def psh_fcf_proj_cdebt (self):
        list1 = self.return_ppe_ave ()
        list2 = self.psh_ppec_cdebt ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c-1<0:
                    psh = None
                else:
                    psh = list1[c-1] * list2[c-1]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3
        
    def psh_fcf_proj_cshares (self):
        list1 = self.return_ppe_ave ()
        list2 = self.psh_ppec_cshares ()
        list3 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c-1<0:
                    psh = None
                else:
                    psh = list1[c-1] * list2[c-1]
            except:
                psh = None
            list3.append (psh)
            c = c + 1
        return list3

    def psh_fcf_proj_2d (self):
        list1 = self.psh_fcf_proj_cdebt ()
        list2 = self.psh_fcf_proj_cshares ()
        list3 = []
        list3.append (list1)
        list3.append (list2)
        return list3

        
    def psh_fcf (self):
        list1 = self.psh_fcf_proj_2d ()
        list2 = self.psh_select ()
        list3 = select_option_conv (list1, list2)
        return list3

    def psh_intrinsic_cdebt (self):
        list1 = self.psh_netliq_cdebt ()
        list2 = self.psh_ppec_cdebt ()
        list3 = self.return_ppe_ave ()
        list4 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c-1<0:
                    psh = None
                else:
                    psh = list1[c-1] + 10 * list2[c-1] * list3 [c-1]
            except:
                psh = None
            list4.append (psh)
            c = c + 1
        return list4
        
    def psh_intrinsic_cshares (self):
        list1 = self.psh_netliq_cshares ()
        list2 = self.psh_ppec_cshares ()
        list3 = self.return_ppe_ave ()
        list4 = []
        n_cols = len (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if c-1<0:
                    psh = None
                else:
                    psh = list1[c-1] + 10 * list2[c-1] * list3 [c-1]
            except:
                psh = None
            list4.append (psh)
            c = c + 1
        return list4

    def psh_intrinsic_2d (self):
        list1 = self.psh_intrinsic_cdebt ()
        list2 = self.psh_intrinsic_cshares ()
        list3 = []
        list3.append (list1)
        list3.append (list2)
        return list3
    
    # Selects whether to treat convertibles as debt or shares
    # The assumption resulting in the LOWER intrinsic value is selected
    def psh_select (self):
        list1 = self.psh_intrinsic_2d ()
        list2 = []
        n_cols = num_of_columns (list1)
        c_min = 0
        c_max = n_cols - 1
        c = c_min
        while c <= c_max:
            try:
                if list1 [0][c] < list1 [1][c]:
                    element = 0
                else:
                    element = 1			
            except:
                element = None
            list2.append (element)
            c = c + 1
        return list2
    
    def psh_intrinsic (self):
        list1 = self.psh_intrinsic_2d ()
        list2 = self.psh_select ()
        list3 = select_option_conv (list1, list2)
        return list3
        
    def psh_netliq (self):
        list1 = self.psh_netliq_2d ()
        list2 = self.psh_select ()
        list3 = select_option_conv (list1, list2)
        return list3

    def doppler_earnings (self):
        list1 = self.psh_ppec ()
        list2 = self.return_ppe_ave ()
        fcf = list1 [-1] * list2 [-1]
        return fcf

    def doppler_book (self):
        doppler_earnings_local = self.doppler_earnings ()
        list1 = self.psh_netliq ()
        bv = 10 * doppler_earnings_local + list1 [-1]
        return bv
    
    def doppler_pb (self):
        p = price
        bv = self.doppler_book ()
        pb = p/bv
        return pb
    
    def doppler_price_adj (self):
        p = price
        list1 = self.psh_netliq ()
        netliq = list1 [-1]
        price_adj = p - netliq
        return price_adj
            
    def doppler_pe (self):
        p_adj = self.doppler_price_adj ()
        fcf = self.doppler_earnings ()
        pe = p_adj / fcf
        return pe
    
    def doppler_eyld (self):
        pe = self.doppler_pe ()
        yld = 1/pe
        return yld

#########################################################
# PART 10: DEFINE THE FUNCTIONS FOR DISPLAYING THE OUTPUT
#########################################################

# Displays the header row of an HTML table
def row_header (str_symbol, str_path, str_name, float_price, int_n):
    mystock = Stock (str_symbol, str_path, str_name, float_price, int_n)
    my_years = mystock.years ()
    list_year = my_years
    str_local = ''
    str_local += '\n<TR>'
    str_local += '<TD><B>Item</B></TD>'
    list_year.reverse ()
    for item in list_year:
        str_local += '<TD><B>' + item + '</B></TD>'
    str_local += '\n</TR>'
    return str_local

# Input: floating point number
# Output: string
def row_item (str_title, list_local):
    str_local = ''
    str_local += '\n<TR>'
    str_local += '<TD>' + str_title + '</TD>'
    str_central = ''
    list_local.reverse ()
    for item in list_local:
        try:
            str_central += '<TD>' + format (item, '.2f') + '</TD>'
        except:
            str_central += '<TD>N/A</TD>'
    str_local = str_local + str_central
    str_local += '\n</TR>'
    return str_local

# Input: floating point number
# Output: string
def psh2 (n_local):
    try:
        x = n_local
        str_local = format (x, '.2f')
    except:
        str_local = 'N/A'
    return str_local
    
def row_item_psh2 (str_title, list_local):
    str_local = ''
    str_local += '\n<TR>'
    str_local += '<TD>' + str_title + '</TD>'
    list_local.reverse ()
    for item in list_local:
        str_local += '<TD>' + psh2 (item) + '</TD>'
    str_local += '\n</TR>'
    return str_local

def psh3 (n_local):
    try:
        x = n_local
        str_local = format (x, '.3f')
    except:
        str_local = 'N/A'
    return str_local
    
def row_item_psh3 (str_title, list_local):
    str_local = ''
    str_local += '\n<TR>'
    str_local += '<TD>' + str_title + '</TD>'
    list_local.reverse ()
    for item in list_local:
        str_local += '<TD>' + psh3 (item) + '</TD>'
    str_local += '\n</TR>'
    return str_local

# Input: floating point number
# Output: string
def percent (n_local):
    try:
        x = n_local
        str_local = format (100*x, '.1f') + '%'
    except:
        str_local = 'N/A'
    return str_local

def row_item_percent (str_title, list_local):
    str_local = ''
    str_local += '\n<TR>'
    str_local += '<TD>' + str_title + '</TD>'
    list_local.reverse ()
    for item in list_local:
        str_local += '<TD>' + percent (item) + '</TD>'
    str_local += '\n</TR>'
    return str_local

def millions (n_local):
    try:
        x = n_local
        x = x * 1E-6
        str_local = format (x, '.1f')
    except:
        str_local = 'N/A'
    return str_local
    
def row_item_millions (str_title, list_local):
    str_local = ''
    str_local += '\n<TR>'
    str_local += '<TD>' + str_title + '</TD>'
    list_local.reverse ()
    for item in list_local:
        str_local += '<TD>' + millions (item) + '</TD>'
    str_local += '\n</TR>'
    return str_local

def output_main (str_symbol, str_path, str_name, float_price, int_n):
    mystock = Stock (str_symbol, str_path, str_name, float_price, int_n)
    if not (os.path.exists(dir_output_stock)):
        os.mkdir (dir_output_stock)
    file_output = dir_output_stock + '/' + str_symbol + '.html'
    f = open(file_output, 'w')
    f.write ('<HTML><BODY>\n')
    
    f.write ('<H1>' + str_name + '</H1>')
    now = datetime.datetime.now()
    f.write ('Date of Report: ' + now.strftime("%Y-%m-%d"))
    f.write ('\n<BR>Symbol: ' + str_symbol.upper())
    f.write ('\n<BR>Name: ' + str_name)
    
    # TABLE OF VALUATION DATA
    my_pb = mystock.doppler_pb ()
    my_pe = mystock.doppler_pe ()
    my_eyld = 100*mystock.doppler_eyld ()
    my_bv = mystock.doppler_book ()
    my_price_adj = mystock.doppler_price_adj ()
    my_fcf = mystock.doppler_earnings ()
    
    f.write ('\n<H3>Current Valuation Data</H3>')
    f.write ('\n<TABLE border=1>')
    f.write ('\n<TR><TD>Recent Stock Price</TD><TD>${0:.2f} per share</TD></TR>'.format (float_price))
    f.write ('\n<TR><TD>Doppler Price/Book Ratio</TD><TD>{0:.2f}</TD></TR>'.format (my_pb))
    f.write ('\n<TR><TD>Doppler PE Ratio</TD><TD>{0:.1f}</TD></TR>'.format (my_pe))
    f.write ('\n<TR><TD>Doppler Earnings Yield</TD><TD>{0:.2f}%</TD></TR>'.format (my_eyld))
    f.write ('\n<TR><TD>Doppler Book Value</TD><TD>${0:.2f} per share</TD></TR>'.format (my_bv))
    f.write ('\n<TR><TD>Price (Adjusted for Net Liquidity)</TD><TD>${0:.2f} per share</TD></TR>'.format (my_price_adj))
    f.write ('\n<TR><TD>Doppler Earnings</TD><TD>${0:.3f} per share</TD></TR>'.format (my_fcf))
    f.write ('\n</TABLE border>') 
    
    # TABLE OF PER-SHARE DATA
    f.write ('\n<H3>Per Share Values</H3>')
    f.write ('\n<TABLE border=1>')
    f.write (row_header(str_symbol, str_path, str_name, float_price, int_n))
    
    my_intrinsic = mystock.psh_intrinsic ()
    f.write (row_item_psh2 ('Intrinsic Value', my_intrinsic))
    
    my_netliq = mystock.psh_netliq ()
    f.write (row_item_psh2 ('Net Liquidity', my_netliq))
    
    my_fcf = mystock.psh_fcf ()
    f.write (row_item_psh3 ('Projected Free Cash Flow', my_fcf))
    # my_fcf_cdebt = mystock.psh_fcf_smooth_cdebt ()
    # f.write (row_item_psh3 ('Smoothed<BR>Free Cash Flow<BR>(No Conversions)', my_fcf_cdebt))
    # my_fcf_cshares = mystock.psh_fcf_smooth_cshares ()
    # f.write (row_item_psh3 ('Smoothed<BR>Free Cash Flow<BR>(With Conversions)', my_fcf_cshares))
    
    my_psh_ppec = mystock.psh_ppec ()
    f.write (row_item_psh3 ('Plant/Property/Equipment', my_psh_ppec))
    
    f.write ('\n</TABLE border>')
    
    # TABLE OF PERFORMANCE DATA
    my_return_ppe = mystock.return_ppe ()
    my_return_ppe_ave = mystock.return_ppe_ave ()
    
    f.write ('\n<H3>Performance</H3>')
    f.write ('\n<TABLE border=1>')
    f.write (row_header(str_symbol, str_path, str_name, float_price, int_n))
    
    f.write (row_item_percent ('Return<BR>on PPE', my_return_ppe))
    
    f.write (row_item_percent ('Smoothed<BR>Return<BR>on PPE', my_return_ppe_ave))
    
    f.write ('\n</TABLE>')
    
    # TABLE OF SHARES OUTSTANDING
    mysplitf = mystock.split_f ()
    myshares_nc = mystock.shares_cdebt ()
    myshares_conv = mystock.shares_conv ()
    myshares_adj_nc = mystock.shares_adj_cdebt ()
    myshares_adj_conv = mystock.shares_adj_cshares ()
    
    f.write ('\n<H3>Shares Outstanding</H3>')
    f.write ('\nNOTE: The split factor is in ones.  Everything else is in millions.')
    f.write ('\n<TABLE border=1>')
    f.write (row_header(str_symbol, str_path, str_name, float_price, int_n))
    f.write (row_item ('Split<BR>Factor', mysplitf))
    f.write (row_item_millions ('Nominal<BR>Shares<BR>(nonconvertible)', myshares_nc))
    f.write (row_item_millions ('Nominal<BR>Shares<BR>(convertible)', myshares_conv))
    f.write (row_item_millions ('Adjusted<BR>Shares<BR>(No Conversions)', myshares_adj_nc))
    f.write (row_item_millions ('Adjusted<BR>Shares<BR>(With Conversions)', myshares_adj_conv))
    f.write ('\n</TABLE>')
    
    # TABLE OF BALANCE SHEET DATA
    myliquid = mystock.dollars_liq ()
    myliab = mystock.dollars_liab_cshares ()
    myliabc = mystock.dollars_liab_conv ()
    mynetliqnc = mystock.dollars_netliq_cshares ()
    mynetliqconv = mystock.dollars_netliq_cdebt ()
    f.write ('\n<H3>Balance Sheet (in millions of dollars)</H3>')
    
    f.write ('\n<TABLE border=1>')
    f.write (row_header(str_symbol, str_path, str_name, float_price, int_n))
    f.write (row_item_millions ('Liquid Assets', myliquid))
    f.write (row_item_millions ('Liabilities -<BR>Nonconvertible', myliab))
    f.write (row_item_millions ('Liabilities -<BR>Convertible', myliabc))
    f.write (row_item_millions ('Net Liquid Assets -<BR>No Conversions', mynetliqnc))
    f.write (row_item_millions ('Net Liquid Assets -<BR>With Conversions', mynetliqconv))
    
    f.write ('\n</TABLE border=1>')
    
    # TABLE OF PLANT/PROPERTY/EQUIPMENT DATA
    myppec = mystock.dollars_ppec ()
    mycap = mystock.dollars_cap ()
    f.write ('\n<H3>Plant/Property/Equipment Capital (in millions of dollars)</H3>')
    f.write ('\n<TABLE border=1>')
    f.write (row_header(str_symbol, str_path, str_name, float_price, int_n))
    f.write (row_item_millions ('Plant/Property/Equipment<BR>Capital', myppec))
    f.write (row_item_millions ('Normalized<BR>Capital<BR>Spending', mycap))
    f.write ('\n</TABLE border=1>')
    
    # TABLE OF CASH FLOW DATA
    my_cfo = mystock.dollars_cfo ()
    my_cftax = mystock.dollars_cftax ()
    my_cfn2f = mystock.dollars_cfn2f ()
    my_cfp2f = mystock.dollars_cfp2f ()
    my_cfp2i = mystock.dollars_cfp2i ()
    my_cfn2i = mystock.dollars_cfn2i ()
    my_cf2o = mystock.dollars_cf2o ()
    my_cf = mystock.dollars_cf ()
    my_cap = mystock.dollars_cap ()
    my_fcf = mystock.dollars_fcf ()

    f.write ('\n<H3>Cash Flow Data (in millions of dollars)</H3>')
    f.write ('\n<TABLE border=1>')
    f.write (row_header(str_symbol, str_path, str_name, float_price, int_n))
    f.write (row_item_millions ('Official<BR>Cash<BR>Flow', my_cfo))
    f.write (row_item_millions ('Income<BR>Tax', my_cftax))
    f.write (row_item_millions ('Costs<BR>(to F)', my_cfn2f))
    f.write (row_item_millions ('Losses<BR>(to I)', my_cfn2i))
    f.write (row_item_millions ('Income<BR>(to F)', my_cfp2f))
    f.write (row_item_millions ('Gains<BR>(to I)', my_cfp2i))
    f.write (row_item_millions ('I/F to O', my_cf2o))
    f.write (row_item_millions ('Pre-tax<BR>Cash<BR>Flow', my_cf))
    f.write (row_item_millions ('Normalized<BR>Capital<BR>Spending', my_cap))
    f.write (row_item_millions ('Doppler<BR>Earnings', my_fcf))
    f.write ('\n</TABLE>')
    f.write ('\n</BODY></HTML>')
    f.close()


i = 0
i_max = len (list_symbol_found) - 1
while i <= i_max:
    symbol = list_symbol_found [i]
    path = list_path_found [i]
    name = list_name_found [i]
    price = list_price_found [i]
    n_smooth = 4
    #Stock_this = Stock (symbol, path, name, price, n_smooth)
    output_main (symbol, path, name, price, n_smooth)
    i = i + 1

