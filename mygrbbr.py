import os
import wget
import curses
import time
import urllib.parse
from urllib.request import urlopen
from bs4 import BeautifulSoup

# Define a function to clean up URL-encoded characters
def clean_filename(filename):
    replacements = {
        '%27': "'",
        '%20': ' ',
        '%28': '(',
        '%29': ')',
        '%2D': '-',
        '%2E': '.',
        '%5B': '[',
        '%5D': ']',
        '%2C': ',',
		'%21': '!',
    }
    for key, value in replacements.items():
        filename = filename.replace(key, value)
    return filename

# Function to display an animated download bar
def download_with_progress(url, filename, stdscr):
    response = urlopen(url)
    total_size = int(response.headers['Content-Length'])
    chunk_size = 8192
    downloaded = 0

    with open(filename, 'wb') as f:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            percent = int(downloaded / total_size * 100)

            # Clear the previous download bar
            stdscr.addstr(7, 0, ' ' * 80)
            # Draw the new download bar
            bar = f"[{'#' * (percent // 2)}{' ' * (50 - percent // 2)}] {percent}%"
            stdscr.addstr(7, 0, bar, curses.color_pair(2))
            stdscr.refresh()
            time.sleep(0.1)  # Adjust the speed of the progress bar here

    stdscr.addstr(8, 0, f"Download complete: {filename}", curses.color_pair(3))
    stdscr.refresh()
    stdscr.getch()

# Fetch links, skipping the first 17 and last 3 entries
def fetch_links(url):
    response = urlopen(url)
    soup = BeautifulSoup(response, 'html.parser')
    links = []
    for link in soup.find_all('a'):
        href = link.get('href')
        if href:
            links.append(href)
    # Skip the first 17 and remove the last 3 links
    return links[17:-3]

# Function to select a directory
def directory_selector(stdscr):
    home_dir = os.path.expanduser('~/RetroPie/roms/')
    current_dir = home_dir  # Start in the $HOME/RetroPie/roms/ directory
    selection = 0

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()  # Get current terminal size
        max_columns = (width // 20)  # Adjust column width (20 chars per column)
        column_width = width // max_columns
        entries_per_column = (height - 4)  # Number of visible entries, adjusted for headers and footers

        # Get list of directories and add option to use current directory
        entries = ['..'] + sorted([entry for entry in os.listdir(current_dir) if os.path.isdir(os.path.join(current_dir, entry))])
        entries.append("Use Current Directory")

        num_entries = len(entries)
        num_rows = (num_entries + max_columns - 1) // max_columns  # Number of rows needed for the columns
        column_entries = [entries[i * num_rows: (i + 1) * num_rows] for i in range(max_columns)]

        # Display the title and instructions
        stdscr.addstr(0, 0, "╔══╣ Select a Directory ╠═════════════════════════════════════┐ ", curses.color_pair(1))
        stdscr.addstr(1, 0, "║Current Directory: {current_dir}", curses.color_pair(3))
        stdscr.addstr(2, 0, "╚═════════════════════════════════════════════════════════════┘ ", curses.color_pair(1))
        

        # Display the entries in columns
        for col in range(max_columns):
            for row in range(num_rows):
                index = row + col * num_rows
                if index < num_entries:
                    entry = column_entries[col][row]
                    # Truncate entry if it exceeds column width
                    if len(entry) > column_width - 2:
                        entry = entry[:column_width - 5] + "..."

                    # Highlight the selected entry
                    if index == selection:
                        stdscr.addstr(row + 3, col * column_width, entry, curses.color_pair(2) | curses.A_REVERSE)
                    else:
                        stdscr.addstr(row + 3, col * column_width, entry, curses.color_pair(2))

        stdscr.addstr(height - 2, 0, "░▒▓█ [←] Back | [↑↓] Navigate | [A] Confirm █▓▒░ ", curses.color_pair(1))
        stdscr.refresh()

        key = stdscr.getch()

        # Handle key events
        if key == curses.KEY_UP:
            if selection > 0:
                selection -= 1
            elif selection == 0 and os.path.dirname(current_dir) != current_dir:
                # Go up a directory
                current_dir = os.path.dirname(current_dir)
                selection = 0

        elif key == curses.KEY_DOWN:
            if selection < len(entries) - 1:
                selection += 1
            elif len(entries) > num_rows * max_columns:
                # Scroll down the list if at the bottom and more entries exist
                selection = min(selection + 1, len(entries) - 1)

        elif key == ord('\n'):  # Enter key to confirm selection
            chosen_entry = entries[selection].rstrip('/')
            if chosen_entry == '..':
                # Go up a directory
                current_dir = os.path.dirname(current_dir)
                selection = 0
            elif os.path.isdir(os.path.join(current_dir, chosen_entry)):
                current_dir = os.path.join(current_dir, chosen_entry)  # Go down into the directory
                selection = 0
            elif chosen_entry == "Use Current Directory":
                return current_dir  # Return the current directory
            else:
                return os.path.join(current_dir, chosen_entry)  # Return the selected directory

        elif key == curses.KEY_LEFT:  # 'left' key to quit
            return None  # Exit without selecting a directory


# Function to scrape and display a new page of links
def scrape_and_display_page(url, stdscr):
    page_links = fetch_links(url)
    PAGE_SIZE = 20
    current_page = 0
    selected_option = 0

    while True:
        display_page(stdscr, page_links, current_page, PAGE_SIZE, selected_option)

        key = stdscr.getch()

        # Handle navigation and selection
        if key == curses.KEY_DOWN:
            if selected_option < PAGE_SIZE - 1 and selected_option < len(page_links) - 1:
                selected_option += 1
            elif (current_page + 1) * PAGE_SIZE < len(page_links):
                current_page += 1
                selected_option = 0

        elif key == curses.KEY_UP:
            if selected_option > 0:
                selected_option -= 1
            elif current_page > 0:
                current_page -= 1
                selected_option = PAGE_SIZE - 1

        elif key == ord('\n'):  # Enter key to confirm selection
            selected_link = page_links[current_page * PAGE_SIZE + selected_option]
            full_url = urllib.parse.urljoin(url, selected_link)  # Construct the full URL

            # Check if the link is a file
            if selected_link.lower().endswith('.zip'):
                # Directory selection for file download
                download_dir = directory_selector(stdscr)
                if download_dir:
                    filename = clean_filename(selected_link)
                    file_path = os.path.join(download_dir, filename)
                    
                    # Start the download and show progress bar
                    stdscr.addstr(10, 0, f"Downloading: {filename}", curses.color_pair(3))
                    stdscr.refresh()
                    download_with_progress(full_url, file_path, stdscr)

                # Refresh the page links after download
                page_links = fetch_links(url)
                current_page = 0
                selected_option = 0
            else:
                stdscr.addstr(10, 0, f"Selected: {clean_filename(selected_link)}", curses.color_pair(3))
                stdscr.refresh()
                stdscr.getch()  # Wait for a key press before continuing

                # Call the scraping function with the new URL
                scrape_and_display_page(full_url, stdscr)

        elif key == curses.KEY_LEFT:  # Quit key assignment to left arrow
            break

def intro_animation(stdscr):
    intro_text = [
        #"  __  __          ____        _      _          ",
        #" |  \/  | _   _  / ___| _ __ | |__  | |__   _ __ ",
        #" | |\/| || | | || |  _ | '__|| '_ \ | '_ \ | '__|",
        #" | |  | || |_| || |_| || |   | |_) || |_) || |   ",
        #" |_|  |_| \__, | \____||_|   |_.__/ |_.__/ |_|   ",
        #"          |___/                                 "
		" ███▄ ▄███▓▓██   ██▓  ▄████  ██▀███   ▄▄▄▄    ▄▄▄▄    ██▀███  ",
		"▓██▒▀█▀ ██▒ ▒██  ██▒ ██▒ ▀█▒▓██ ▒ ██▒▓█████▄ ▓█████▄ ▓██ ▒ ██▒",
		"▓██    ▓██░  ▒██ ██░▒██░▄▄▄░▓██ ░▄█ ▒▒██▒ ▄██▒██▒ ▄██▓██ ░▄█ ▒",
		"▒██    ▒██   ░ ▐██▓░░▓█  ██▓▒██▀▀█▄  ▒██░█▀  ▒██░█▀  ▒██▀▀█▄  ",
		"▒██▒   ░██▒  ░ ██▒▓░░▒▓███▀▒░██▓ ▒██▒░▓█  ▀█▓░▓█  ▀█▓░██▓ ▒██▒",
		"░ ▒░   ░  ░   ██▒▒▒  ░▒   ▒ ░ ▒▓ ░▒▓░░▒▓███▀▒░▒▓███▀▒░ ▒▓ ░▒▓░",
		"░  ░      ░ ▓██ ░▒░   ░   ░   ░▒ ░ ▒░▒░▒   ░ ▒░▒   ░   ░▒ ░ ▒░",
		"░           ▒ ▒ ░░    ░   ░   ░░   ░  ░    ░  ░    ░   ░░   ░ ",
		"░           ▒[ Myrient Scraper & Downloader ] [ Version 1.0b ]",
		"░           ▒ ▒ ░░    ░   ░   ░░   ░  ░    ░  ░    ░   ░░   ░ "
		]
    stdscr.clear()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    for i, line in enumerate(intro_text):
        stdscr.addstr(i + 2, 5, line, curses.color_pair(2))
        stdscr.refresh()
        time.sleep(0.3)

    time.sleep(1)
    stdscr.clear()

# Updated display function with placeholder text for second title line
def display_page(stdscr, page_links, current_page, PAGE_SIZE, selected_option):
    height, width = stdscr.getmaxyx()
    start_index = current_page * PAGE_SIZE
    end_index = min(start_index + PAGE_SIZE, len(page_links))

    stdscr.clear()

    # Display the title with a second line in yellow
    stdscr.addstr(0, 0, "╔══╣ MyGrbbr - A Myriant Scraper ╠══════════════════════════════╗", curses.color_pair(1))
    stdscr.addstr(1, 0, "║[←] Back | [↑↓] Navigate | [A] Confirm                         ║", curses.color_pair(3))
    stdscr.addstr(2, 0, "╚═══════════════════════════════════════════════════════════════╝", curses.color_pair(1))

    # Display the list of links
    for i in range(start_index, end_index):
        line = f"{i - start_index + 1}: {clean_filename(page_links[i])}"
        if i == start_index + selected_option:
            stdscr.addstr(i - start_index + 3, 0, line, curses.color_pair(2) | curses.A_REVERSE)
        else:
            stdscr.addstr(i - start_index + 3, 0, line, curses.color_pair(2))

    stdscr.refresh()

# Main program entry
def main(stdscr):
    # Setup
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    # Show intro animation
    intro_animation(stdscr)

    # Initialize state
    current_page_url = 'https://myrient.erista.me/files/No-Intro/'
    scrape_and_display_page(current_page_url, stdscr)

if __name__ == "__main__":
    curses.wrapper(main)
