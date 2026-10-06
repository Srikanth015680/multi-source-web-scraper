
# Multi-Source Web Scraping & Data Consolidation

A Python pipeline that scrapes two public sandbox sites, **Books to Scrape** and **Quotes to Scrape**, and combines them into one cleaned, validated and deduplicated dataset with a summary report.

## Project Overview

The two sites have different structures. Books contain prices, ratings and categories, while quotes contain authors and tags. The pipeline collects data from both sources, maps everything into one common schema, cleans and validates the records, removes duplicates, and produces a single CSV dataset along with a JSON summary report.

Rejections, duplicates and scraping failures are counted and reported instead of being silently dropped.

## Architecture

```text
Books to Scrape ─┐
                 ├─> Scraping -> Cleaning -> Validation -> Deduplication -> Consolidation -> Output
Quotes to Scrape ┘
```
# multi-source-web-scraper
