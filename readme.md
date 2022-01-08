# Hello and welcome to Project Groceryper!

*The goal: answer the question of "Is this week's flyer special actually good or not?"*

How?  By cross-checking the price against what it has been in the past.

## Introduction

This is a spin-off and expansion upon a flyer scraping script [originally developed
by Sensanmu](https://www.reddit.com/r/learnpython/comments/el0v78/grocery_flyer_scrapper_metro_canada/).
I have adapted it to my own purposes, and added some features to better handle less-than-straightforward
specials, especially around meat, fruit, and vegetables.

I tried my best to make this script as portable as possible.  There is still much room for improvement
of course - let's just say this isn't what I'd submit at a dev job interview.

**This script is meant to run in Python 3.6, and requires a recent installation of Mozilla Firefox.**

**CAUTION!** At the moment, the script is mostly geared towards interpreting flyers written in French.

For the script to work for yourself, you will need to perform a first-time setup in the *main.py* file.
The setup proper is explained in greater detail there.

The script outputs a text file with one flat JSON on each line, and meant to be imported into ElasticSearch.
Each entry will contain, at minimum, the following fields:
* `date` - Today's date, used to indicate the flyer run date.
* `item_name` - Name of the product on special
* `unit_price` - Price of the product on special
* `original_text_price` - How the price was expressed as-is in the flyer.  Included for debugging purposes.
* `store_name` - Store that sells the product on special

Additional fields that may or may not show up are:
* `is_multi` - True if the special applies only if you purchase multiples of an item (ex.: "3 for 1$")
* `multi_quantity` - The required quantity to purchase to activate the special.
* `multi_total_price` - The special price for that quantity (ex.: the 1$ in "3 for 1$")
* `multi_unit_price` - The special price, per-unit.
* `unit_price_if_multi` - The non-special price were you to purchase the required quantity of it.
  * Applies in instances such as "3 for 1$, or 50 cents per", in this here case this value would be 3*50 cents, or 1.50$
* `is_weight` - True if the special is per weight rather than per unit.
* `unit` - The unit of measurement if it's not per item.  (Ex.: lb, ml, etc.)
* `is_minimum` - True if the price contains a clause such as "Starting at..."

-----------------------

## Flyer Cross-Check: The Full Loop

1. Install [ElasticSearch and Kibana](https://www.elastic.co).  The free version can be installed on your local machine.
2. Run the script.  It will produce a text file whose name is "flyer" followed by today's date.
3. With ElasticSearch and Kibana running, log into Kibana, and import the text file using the Machine Learning > Data Visualizer tool.  Import the data into an index that's of the same name as the text file's name.
4. Navigate to Kibana's Dev Tools interface, and run the following query:

```
GET flyer*/_search
{
  "size": 25,
  "query": {
    "function_score": {
      "query": {
        "match": {
          "item_name": {
            "query": "your item name here"
          }
        }
      },
      "functions": [
        {
          "exp": {
            "unit_price": {
              "origin": 0,
              "scale": "50"
            }
          }
        }
      ]
    }
  }
}
```

Since we can use wildcards in the index names we want to search on, we can thus import each flyer
into its own index, and get around Kibana's limitation of refusing to import into existing indexes
using the Data Visualizer.

The query is structured so as to primarily search for the item you wish (works natively in both English
and French) while also applying a bit of scoring weight on the price.  Items of the same/similar name but
with a price closer to zero basically earn bonus points.  The `scale` value is a way to tweak at which point
the score should severely drop (in the above query, it's set to 50$.)  You will most likely have to use
a different value depending on the sort of item you're looking for.  It goes without saying that the
cutoff price for a thick juicy AAA bone-in ribeye steak is quite different from that of a handful of lemons.

This way, you can now look at the price for a Filet of Something this week, and see if the price has been
better in the past, where, when, and in which manner.