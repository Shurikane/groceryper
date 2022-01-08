import os
import time
import simplejson
import traceback

from datetime import date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.firefox_binary import FirefoxBinary
from re import sub
from decimal import Decimal


# ----------------------------------------------------------
# FIRST-TIME SETUP:
# ----------------------------------------------------------
# First, specify where your Firefox installation is located.  Kindly convert backslashes (\) to slashes (/).
firefox_exec_location = 'C:/Program Files/Mozilla Firefox/firefox.exe'

# Next, paste the store name and the URL of every flyer you wish to scrape.
# In this example, I went through circulaires.ca to obtain these URLs.  Your personal mileage may vary.
# Just copy-paste whatever showed up in your address bar when you navigated to each flyer by yourself.
# No need to upload the URLs weekly: they'll always point to the current run.
# Compatible with: Adonis, IGA, Métro, Les Marchés Tradition, Maxi, Provigo, Super C
# In general, if it's powered by Flipp and is fully interactive (i.e.: clickable items and not just pictures),
# then it should work.
flyers_dict = {
    'adonis': 'https://ecirculaire.groupeadonis.ca/flyers/marcheadonis-flyerflipweekly?flyer_run_id=657412&auto_locate=true&locale=fr&postal_code=H1L3N6&store_code=109&type=1#!/flyers/marcheadonis-flyerflipweekly?flyer_run_id=657412',
    'iga': 'https://flyers.iga.net/flyers/igaquebec-quebec?flyer_run_id=641893&auto_locate=true&hide=special%2Cpub&locale=fr&store_code=8253&type=1#!/flyers/igaquebec-quebec?flyer_run_id=641893',
    'tradition': 'https://circulaire.marchestradition.com/flyers/lesmarchstradition-flyer?flyer_run_id=645717&auto_locate=true&auto_store=true&locale=fr&postal_code=H1L1A1&type=1#!/flyers/lesmarchstradition-flyer?flyer_run_id=645717',
    'maxi': 'https://flyers.maxi.ca/flyers/maxi-flyer?flyer_run_id=650796&auto_locate=true&locale=fr&postal_code=H1L3N6&store_code=8910&type=1#!/flyers/maxi-flyer?flyer_run_id=650796',
    'metro': 'https://ecirculaire.metro.ca/flyers/metro-circulaire?flyer_run_id=660668&auto_locate=true&locale=fr&postal_code=H1L3L2&store_code=152&type=1#!/flyers/metro-circulaire?flyer_run_id=660668',
    'provigo': 'https://flyers.provigo.ca/flyers/provigo-flyer?flyer_run_id=763548&locale=fr&postal_code=H1L3N6&store_code=8896&type=1#!/flyers/provigo-flyer?flyer_run_id=763548',
    'super c': 'https://ecirculaire.superc.ca/flyers/superc-circulaire?flyer_run_id=651646&auto_locate=true&locale=fr&postal_code=H1L3N6&store_code=5904&type=1#!/flyers/superc-circulaire?flyer_run_id=651646'
}

# Finally, specify the output folder where you'd like the results to appear.
output_folder = 'G:/'

# That's it!  If all goes well, the output will go into a file named 'flyer' along with the today's date.

# ======================================================================================================================
# ======================================================================================================================
# ======================================================================================================================


# Get today's date, this will be used to fill in data and the file name.
today = date.today().__str__()

# Determine the regular expression to parce a price entry down to just a decimal number.
pricing_regex = r'[^0-9\d\-.]'


def process_flyer(flyer_name):
    flyer_price_arr = []

    print('Collecting Data for: ' + flyer_name + '...')

    browser_driver = webdriver.Firefox(firefox_binary=binary, executable_path=gecko + '.exe')

    # Load a browser window with the chosen flyer.
    browser_driver.get(flyers_dict[flyer_name].replace('?flyer_run_id=', '/grid_view/').replace('&', '?', 1))

    # Put script to sleep to leave time for the browser to load the page.
    time.sleep(3)

    # Collect data and combine into an item/prices dictionary.
    # First, the item names.
    item_name_arr = []
    for item in browser_driver.find_elements_by_class_name('item-name'):
        item_name_arr.append(item.text.strip().upper())

    # Next, the item prices.
    # The aria-label element isn't enough because it strips away important info about quantities and weights.
    # So, we have to dig deeper.
    item_price_arr = []
    for item in browser_driver.find_elements_by_class_name('item-price'):
        item_price_arr.append(item.text.strip().upper())

    # Now to combine that raw input into a dictionary for easier handling down the line.
    raw_items_dict = dict(zip(item_name_arr, item_price_arr))

    # So, the price is a piece of shit.
    # First we have basic prices, like 17,99$
    # Then we have multiplier prices like 2/ 10,99$
    # And finally we have "Starting from" 20,99$
    # And then there's all this pound and kilogram and per 100g stuff
    # And I didn't even go into liquid quantities yet!
    # Last but not least, items that are more expensive unless you buy multiples of them.
    # Jesus H Christ.  I swear to God.
    # The code below is likely to demand multiple revisions as I bump into each store's way of writing prices.
    # It will never truly cover all the possible cases, as there is no standard in flyer-making.
    # ALSO, RIGHT NOW, THIS HANDLES THE FRENCH LANGUAGE.  ADAPT TO YOUR OWN LANGUAGE AND/OR YOUR STORES' LINGO.
    for item in raw_items_dict.items():

        # If we're missing the item name or price, then no need to add it to the list.  It's probably just a coupon.
        # Same if the price doesn't contain a dollar sign; this usually indicates a "see price in store" clause.
        # By the way, "see price in store" is bullshit.  Thanks for nothing, Maxi.
        if item[0] == '' or item[1] == '' or '$' not in item[1]:
            continue

        # Initialize the entry with the bare essentials.
        # Also separate a few common ligatures, as ElasticSearch deals a bit strangely with them, I think.
        price_entry_dict = {
            'item_name': item[0].replace("Œ", "OE").replace("Æ", "AE"),
            'original_text_price': item[1],
            'date': today,
            'store_name': flyer_name
        }

        # Sanitize the item_price_text a bit, otherwise there are too many possibilities to account for.
        # The things I'm taking away here don't affect the end result, and simplify the parsing job further below.
        item_price_text = item[1] \
            .replace('CH./EA.', '') \
            .replace('CH.', '') \
            .replace('EA.', '') \
            .replace('/UN.', '')

        try:
            if '/ ' in item_price_text:
                # CASE: It's a quantity thing (Ex.: 2 for 5.00$)
                multi_quantity = Decimal(sub(pricing_regex, '', item_price_text[:item_price_text.index('/')]))

                if ' OU ' in item_price_text:
                    # Sometimes the price also lists what each unit costs if one doesn't buy the requisite amount.
                    multi_total_price = Decimal(
                        sub(pricing_regex, '',
                            item_price_text[item_price_text.index(' '):item_price_text.index('$')].replace(',', '.')))

                    unit_label = item_price_text[item_price_text.index(' OU '):]
                    if '/' in unit_label:
                        # This is a from-to price for multiple items.
                        # I'll take the lower one and claim it's "starting at".
                        price_entry_dict['is_minimum'] = True
                        raw_unit_price = Decimal(
                            sub(pricing_regex, '', unit_label[:unit_label.index('/')]
                                .replace('CH.', '')
                                .replace(',', '.')))
                    else:
                        raw_unit_price = Decimal(
                            sub(pricing_regex, '', unit_label.replace('CH.', '').replace(',', '.')))

                    raw_unit_price_if_multi = raw_unit_price * multi_quantity

                    price_entry_dict['unit_price'] = raw_unit_price
                    price_entry_dict['unit_price_if_multi'] = raw_unit_price_if_multi
                else:
                    # If the unit cost isn't specified, default to whatever the special price is, since the
                    # 'unit_price' field is considered a bare essential.
                    multi_total_price = Decimal(
                        sub(pricing_regex, '',
                            item_price_text[item_price_text.index(' '):item_price_text.index('$')].replace(',', '.')))
                    price_entry_dict['unit_price'] = multi_total_price / multi_quantity
                    price_entry_dict['unit_price_if_multi'] = multi_total_price

                multi_unit_price = multi_total_price / multi_quantity

                # Flag the document as requiring a quantity-multiple for the special to work.
                price_entry_dict['is_multi'] = True
                price_entry_dict['multi_quantity'] = multi_quantity
                price_entry_dict['multi_total_price'] = multi_total_price
                price_entry_dict['multi_unit_price'] = multi_unit_price
            elif '/LB' in item_price_text:
                # CASE: It's a weight, mark it as such.
                price_entry_dict['is_weight'] = True
                price_entry_dict['unit_price'] = Decimal(
                    sub(pricing_regex, '', item_price_text[:item_price_text.index('/')].replace(',', '.')))
                price_entry_dict['unit'] = 'lb'
            elif '/KG' in item_price_text:
                # CASE: It's a weight, mark it as such.
                # I'm converting all weights to pounds (lb)
                price_entry_dict['is_weight'] = True
                price_entry_dict['unit_price'] = Decimal(
                    sub(pricing_regex, '', item_price_text[:item_price_text.index('/')].replace(',', '.'))) \
                                                 * Decimal(0.45359237)
                price_entry_dict['unit'] = 'lb'
            elif 'LE 100 G' in item_price_text or '/100G' in item_price_text:
                # CASE: It's a weight, mark it as such.
                # I'm converting all weights to pounds (lb)
                price_entry_dict['is_weight'] = True
                price_entry_dict['unit_price'] = Decimal(
                    sub(pricing_regex, '', item_price_text[:item_price_text.index('G') + 1]
                        .replace('LE 100 G', '')
                        .replace('/100G', '')
                        .replace(',', '.'))) \
                                                 * 10 * Decimal(0.45359237)
                price_entry_dict['unit'] = 'lb'
            elif 'À PARTIR DE' in item_price_text:
                # CASE: The price listed is a "starting at".  Mark it as such.
                price_entry_dict['is_minimum'] = True
                price_entry_dict['unit_price'] = Decimal(
                    sub(pricing_regex, '',
                        item_price_text[item_price_text.index(' '):].replace(',', '.').strip('$').strip()))
            elif 'A/' in item_price_text:
                # CASE: This is a from-to price for multiple items.
                # I'll take the lower one and claim it's "starting at".
                price_entry_dict['is_minimum'] = True
                price_entry_dict['unit_price'] = Decimal(
                    sub(pricing_regex, '', item_price_text[:item_price_text.index('/')].replace(',', '.')))
            else:
                # CASE: The best of all cases: a plain ol' special price, nothing fancy, thank goodness.
                if item_price_text != '':
                    price_entry_dict['unit_price'] = Decimal(
                        sub(pricing_regex, '', item_price_text.replace(',', '.').replace('CH.', '')))
        except:
            # Sure, a maximum-broad exception isn't ideal, but still, I want to add a bit of context along with
            # the usual stack trace.  This'll make debugging much easier if something explodes along the way.
            print('STOPPING PROGRAM: Error encountered when interpreting item: ' + item[0]
                  + ' with price: ' + item_price_text)
            traceback.print_exc()
            browser_driver.quit()
            exit(-1)

        flyer_price_arr.append(price_entry_dict)

    # Job's done, close the browser window.
    browser_driver.quit()
    return flyer_price_arr


if __name__ == '__main__':
    # Init Firefox browser drivers.
    options = Options()
    options.add_argument('disable-infobars')
    gecko = os.path.normpath(os.path.join(os.path.dirname(__file__), 'geckodriver'))
    binary = FirefoxBinary(firefox_exec_location)

    price_arr = []
    for flyer in flyers_dict.keys():
        price_arr += process_flyer(flyer)

    # Export the results to a text file
    # Each entry within the file consists of a denormalized (flat) JSON meant for feeding into ElasticSearch.
    print('Writing to file...')
    os.chdir(output_folder)
    writeto_file = 'flyer' + today + '.txt'
    with open(writeto_file, 'w', encoding='utf-8') as file:
        for price_document in price_arr:
            file.write(simplejson.dumps(price_document, indent=None, ensure_ascii=False) + '\n')

    print('Data capture successful.  Processing complete.')
