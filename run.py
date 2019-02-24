#!usr/bin/env python3.7


import asyncio
import argparse
import logging
from http import HTTPStatus

import os
from bs4 import BeautifulSoup
import aiohttp


async def get_page_content(session: aiohttp.ClientSession, url: str,
                           retries=10, retry_timeout=2, logger=None) -> bytes:
    page_content = b''
    if not logger:
        logger = logging

    while retries > 0:
        try:
            response = await session.get(url)

        except asyncio.CancelledError:
            logger.error(f'Fetching url: {url} was canceled')
        except:
            logger.exception(f'An error while getting: {url}. Retrying...')
            retries -= 1
            await asyncio.sleep(retry_timeout)
            continue
        else:
            if response.status == HTTPStatus.OK:
                page_content = await response.read()
            elif response.status >= HTTPStatus.BAD_REQUEST:
                logger.error(f"Received {response.status} error on getting url: {url} Retrying...")
                retries -= 1
                await asyncio.sleep(retry_timeout)
                continue

            response.close()
            return page_content


def get_links_on_lessons(page_content: BeautifulSoup,
                         course_url_css='ul#lessons-list li link[itemprop="contentUrl"]',
                         course_title_css='ul#lessons-list li span[itemprop="name"]') -> dict:
    urls = page_content.select(course_url_css)
    titles = page_content.select(course_title_css)
    return {title.text: url['href'] for title, url in zip(titles, urls)}


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Get videos from coursehunters.net'
    )
    parser.add_argument(
        'course_url',
        type=str,
        help='A course link on coursehunters.net site'
    )
    parser.add_argument(
        '-o', '--output-folder',
        type=str,
        help='Path where we save dir with downloaded videos [default=.]',
        metavar='output_folder',
        default='.'
    )
    return parser.parse_args()


async def downloader(args: argparse.Namespace, download_queue, logger=None):
    pass


async def crawler(args: argparse.Namespace, download_queue, logger=None, max_page_timeout=20):
    course_url = args.course_url
    output_path = args.output_folder
    PAGE_TITLE_SELECTOR = 'header div.original-name'
    course_page_html = ''
    session = aiohttp.ClientSession()

    try:
        course_page_html = await asyncio.wait_for(
            get_page_content(session, course_url, logger=logger),
            timeout=max_page_timeout
        )
    except asyncio.TimeoutError:
        logger.error('Error on fetching course page: {course_url}')
    course_page = BeautifulSoup(course_page_html, "html.parser")
    links_on_lessons = get_links_on_lessons(course_page)

    # Get name for output folder
    output_folder = course_page.select_one(PAGE_TITLE_SELECTOR).text
    output_fullpath = os.path.join(output_path, output_folder)

    tasks = []
    for title, url in links_on_lessons.items():
        tasks.append(get_page_content(session, url=url, logger=logger))

    done, pending = await asyncio.wait(tasks)

    await session.close()


if __name__ == '__main__':
    args = get_args()
    download_queue = asyncio.Queue(5)

    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s] %(funcName)s: %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    logger = logging.getLogger('asyncio')
    asyncio.run(
        asyncio.gather(
            crawler(args=args, download_queue=download_queue, logger=logger)
        )
    )
