import random
from enum import Enum
import curses
import time
import os
from pathlib import Path


def debug_log(*args):
    with open("debug.log", "a+") as f:
        print(*args, file=f)


def load_text(dir):
    #   choose a random file from the specified folder to load
    #   and return the text from it

    file_list = [i for i  in Path(dir).glob("**/*") if os.path.isfile(i)]
    filename = random.choice(file_list)

    f = open(filename, 'r')
    text = f.read()
    f.close()

    #replace weird quotes
    text = text.replace("`", "'")#TODO: get a full list of weird quotes to replace
    #remove empty lines
    text = [i+"\n" for i in text.split("\n") if i]

    #TODO: split text thats too long here

    return text


def func(scr):
    #set up stuff for timers
    curses.halfdelay(1)#TODO: consider making this .1 or something so the timer has more resolution

    #allow color use with curses
    curses.start_color()
    curses.use_default_colors()

    #and set some color pairs
    curses.init_pair(1, curses.COLOR_GREEN, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, -1, curses.COLOR_RED)
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_YELLOW)

    #enum to make using pairs easier
    class Colors(Enum):
        DEFAULT = 0
        GREEN = 1
        RED = 2
        RED_BG = 3
        YELLOW = 4


    #separate windows for top bar and input area
    height, width = scr.getmaxyx()
    topbar = curses.newwin(4, width, 0, 0)
    input_area = curses.newwin(9, width, 4, 0)

    #set up topbar
    topbar.addstr(0,4,"Time:")
    topbar.addstr(1,5,"WPM:")
    topbar.addstr(2,0,"Accuracy:")
    topbar.refresh()

    def update_topbar():#FIXME: make the addstr in this section aligned with the offset whatever : >4 or whatever
        nonlocal test_time, countdown_timer, t0
        nonlocal total_chars_typed, uncorrected_errors
        nonlocal correct_characters_typed
        #update timer
        tf = time.time()
        if total_chars_typed > 0: countdown_timer -= tf-t0 #dont count down until typing started
        t0 = tf
        topbar.addstr(0,9,f"{countdown_timer: >6.1f}")

        #update WPM
        elapsed_time = test_time - countdown_timer
        net_wpm = ((total_chars_typed/5) - uncorrected_errors)/(elapsed_time/60) if elapsed_time else 0
        topbar.addstr(1,9,f"{max(net_wpm, 0): >6.1f}")

        #update accuracy

        accuracy = correct_characters_typed / total_chars_typed if total_chars_typed else 0
        topbar.addstr(2,9,f"{accuracy: >6.1%}")

        topbar.refresh()


    #how many lines should pass before overwriting with the next part of the text
    preserved_lines = 3
    #how many lines ahead can you see
    lookahead_lines = input_area.getmaxyx()[0] - preserved_lines
    #furthest line reached so far
    furthest_line = 0

    #load some text
    text = load_text("Texts/")

    #initial display of text
    for y,line in enumerate(text[:input_area.getmaxyx()[0]-1]):
        input_area.addstr(y, 0, line)


    input_area.move(0, 0)
    input_area.refresh()



    #stuff for stats

    #total number of characters typed (excluding backspaces)
    total_chars_typed = 0

    #number of errors that havent been corrected yet
    uncorrected_errors = 0

    #number of characters typed correctly
    correct_characters_typed = 0

    last_pos = ()
    last_correct_ch = ""
    last_character_typed = ""
    check_deletion_phase_shift = False

    #60 second timer
    test_time = 60
    countdown_timer = test_time
    t0 = time.time()

    #start of test section
    line_num = 0
    while line_num < len(text) and countdown_timer > 0:

        y, x = input_area.getyx()

        correct_ch = chr(input_area.inch(y,x) & 0xff)


        if check_deletion_phase_shift and last_character_typed == correct_ch:
            #deletion phase shift correction
            input_area.addstr(*last_pos, last_correct_ch, curses.color_pair(Colors.YELLOW.value))
            input_area.addstr(correct_ch, curses.color_pair(Colors.GREEN.value))

            y, x = input_area.getyx()

            correct_ch = chr(input_area.inch(y,x) & 0xff)

            check_deletion_phase_shift = False
            last_pos = ()


        #TODO: check for screen size change
        input_area_height = input_area.getmaxyx()[0]-1 #setting this every time so I can check for screen size change at some point



        #get input
        try:
            ch = chr(input_area.getch())
            update_topbar()
        except:
            update_topbar()
            continue





        if ord(ch) in (curses.KEY_BACKSPACE,127):#127 as a workaround for macos and maybe some other things
            #backspace
            if x > 0:
                #backspace within a line
                new_pos = (y, x-1)

            elif line_num > 0 and furthest_line - line_num < preserved_lines:
                #backspace to the previous line
                line_num -= 1
                new_pos = ((y-1) % input_area_height, len(text[line_num])-1)

            else:
                continue

            erased_char = input_area.inch(*new_pos)

            if erased_char == curses.color_pair(Colors.RED.value) or erased_char == curses.color_pair(Colors.RED_BG.value):
                #if an error is erased count that as correcting it
                uncorrected_errors -= 1

            #write some stuff and move around (TODO: put a better comment here please)
            input_area.addstr(*new_pos, chr(erased_char & 0xff), curses.color_pair(Colors.DEFAULT.value))
            input_area.move(*new_pos)
            input_area.refresh()

            #clear phase shift vars
            last_pos = ()
            last_correct_ch = ""
            last_character_typed = ""
            check_deletion_phase_shift = False

            continue



        elif ch == correct_ch or (x == len(text[line_num])-1 and ch.isspace()):
            #correct (or whitespace when its technically supposed to be a newline)
            color = Colors.GREEN.value
            total_chars_typed += 1
            correct_characters_typed += 1

            last_pos = ()
            last_correct_ch = correct_ch
            last_character_typed = ""
            check_deletion_phase_shift = False



        else:
            #incorrect
            total_chars_typed += 1

            #debug_log(last_pos)

            if last_pos and ch == last_correct_ch:
                #insertion phase shift correction

                if not last_pos[0] == y:
                    line_num -= 1
                input_area.move(*last_pos)
                (y, x) = last_pos

                color = Colors.YELLOW.value
                correct_ch = ch
                last_pos = ()

            else:
                #no phase shift, just an error

                if last_character_typed == correct_ch:
                    last_pos = (y,x)
                    check_deletion_phase_shift = True

                if ch == last_correct_ch:
                    last_pos = (y,x)

                last_character_typed = ch
                last_correct_ch = correct_ch

                color = Colors.RED.value if not correct_ch.isspace() else Colors.RED_BG.value
                uncorrected_errors += 1



        #move to next line when done with the current line
        if x >= len(text[line_num])-1:
            line_num += 1
            if line_num > furthest_line:
                furthest_line = line_num

                #write next section of text over previous text
                input_area.addstr((y - preserved_lines) % input_area_height, 0, text[line_num + lookahead_lines-2])
                input_area.move(y,x)

            correct_ch = " \n"

            if last_correct_ch:
                last_correct_ch = " \n"


        #update the display
        input_area.addstr(correct_ch, curses.color_pair(color))

        if y >= input_area_height:
            #loop cursor to top of text
            input_area.move(0,0)

        input_area.refresh()



    #idle after time runs out
    #TODO: make something happen here
    while True:
        pass




if __name__ == '__main__':
    curses.wrapper(func)
