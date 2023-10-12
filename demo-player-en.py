import argparse
import os
import math
import random
import sys
import socketio
import time

from rich import print


"""
Constants
"""
# All event names for socket communication
class SocketConst:
    class EMIT:
        JOIN_ROOM = 'join-room'  # Join the match
        RECEIVER_CARD = 'receiver-card'  # Distribute cards
        FIRST_PLAYER = 'first-player'  # Start the match
        COLOR_OF_WILD = 'color-of-wild'  # Change the color of the played card
        UPDATE_COLOR = 'update-color'  # Played card color has changed
        SHUFFLE_WILD = 'shuffle-wild'  # Distribute cards after shuffling
        NEXT_PLAYER = 'next-player'  # Your turn
        PLAY_CARD = 'play-card'  # Play a card
        DRAW_CARD = 'draw-card'  # Draw a card from the deck
        PLAY_DRAW_CARD = 'play-draw-card'  # Play a card drawn from the deck
        CHALLENGE = 'challenge'  # Challenge
        PUBLIC_CARD = 'public-card'  # Publicize hand
        POINTED_NOT_SAY_UNO = 'pointed-not-say-uno'  # Point out UNO declaration omission
        SPECIAL_LOGIC = 'special-logic'  # Special logic
        FINISH_TURN = 'finish-turn'  # End of match
        FINISH_GAME = 'finish-game'  # End of game
        PENALTY = 'penalty'  # Penalty

# Colors of UNO cards
class Color:
    RED = 'red'
    YELLOW = 'yellow'
    GREEN = 'green'
    BLUE = 'blue'
    BLACK = 'black'
    WHITE = 'white'

# Types of special UNO cards
class Special:
    SKIP = 'skip'
    REVERSE = 'reverse'
    DRAW_2 = 'draw_2'
    WILD = 'wild'
    WILD_DRAW_4 = 'wild_draw_4'
    WILD_SHUFFLE = 'wild_shuffle'
    WHITE_WILD = 'white_wild'

# Reasons for drawing cards
class DrawReason:
    DRAW_2 = 'draw_2'
    WILD_DRAW_4 = 'wild_draw_4'
    BIND_2 = 'bind_2'
    SKIP_BIND_2 = 'skip_bind_2'
    NOTING = 'nothing'

TEST_TOOL_HOST_PORT = '3000'  # Port number for development guideline tool
ARR_COLOR = [Color.RED, Color.YELLOW, Color.GREEN, Color.BLUE]  # Options for color change

"""
Variables received from the command line
"""
parser = argparse.ArgumentParser(description='A demo player written in Python')
parser.add_argument('host', action='store', type=str, help='Host to connect')
parser.add_argument('room_name', action='store', type=str, help='Name of the room to join')
parser.add_argument('player', action='store', type=str, help='Player name you join the game as')
parser.add_argument('event_name', action='store', nargs='?', default=None, type=str, help='Event name for test tool')  # Additional

args = parser.parse_args(sys.argv[1:])
host = args.host  # Connection destination (Main system or development guideline tool)
room_name = args.room_name  # Dealer name
player = args.player  # Player name
event_name = args.event_name  # Socket communication event name
is_test_tool = TEST_TOOL_HOST_PORT in host  # Check if the connection destination is the development guideline tool
SPECIAL_LOGIC_TITLE = 'Special Logic Name'  # Special logic name
TIME_DELAY = 10  # Processing pause time

once_connected = False
id = ''  # Your ID
uno_declared = {}  # UNO declaration status of other players

"""
Command line argument check
"""
if not host:
    # If the host destination is not specified, exit the process
    print('Host missed')
    os._exit(0)
else:
    print('Host: {}'.format(host))

# Check if dealer name and player name are specified
if not room_name or not player:
    print('Arguments invalid')

    if not is_test_tool:
        # If the connection destination is the main system, exit the process
        os._exit(0)
else:
    print('Dealer: {}, Player: {}'.format(room_name, player))

# Sample data to be sent in development guideline tool STEP1
TEST_TOOL_EVENT_DATA = {
    SocketConst.EMIT.JOIN_ROOM: {
        'player': player,
        'room_name': room_name,
    },
    SocketConst.EMIT.COLOR_OF_WILD: {
        'color_of_wild': 'red',
    },
    SocketConst.EMIT.PLAY_CARD: {
        'card_play': {'color': 'black', 'special': 'wild'},
        'yell_uno': False,
        'color_of_wild': 'blue',
    },
    SocketConst.EMIT.DRAW_CARD: {},
    SocketConst.EMIT.PLAY_DRAW_CARD: {
        'is_play_card': True,
        'yell_uno': True,
        'color_of_wild': 'blue',
    },
    SocketConst.EMIT.CHALLENGE: {
        'is_challenge': True,
    },
    SocketConst.EMIT.POINTED_NOT_SAY_UNO: {
        'target': 'Player 1',
    },
    SocketConst.EMIT.SPECIAL_LOGIC: {
        'title': SPECIAL_LOGIC_TITLE,
    },
}



# Socket client
sio = socketio.Client()

"""
Select a card to play

Args:
    cards (list): Your hand
    before_card (*): Played card
"""
def select_play_card(cards, before_card):
    cards_valid = []  # Store wild, shuffle wild, and white wild cards
    cards_wild = []  # Store wild draw 4 cards
    cards_wild4 = []  # Store cards of the same color or the same number/symbol

    # Extract cards that can be played by comparing with the played card
    for card in cards:
        card_special = card.get('special')
        card_number = card.get('number')
        if str(card_special) == Special.WILD_DRAW_4:
            # Wild draw 4 can be played regardless of the played card
            cards_wild4.append(card)
        elif (
            str(card_special) == Special.WILD or
            str(card_special) == Special.WILD_SHUFFLE or
            str(card_special) == Special.WHITE_WILD
        ):
            # Wild, shuffle wild, and white wild can also be played regardless of the played card
            cards_wild.append(card)
        elif str(card.get('color')) == str(before_card.get('color')):
            # Cards of the same color as the played card
            cards_valid.append(card)
        elif (
            (card_special and str(card_special) == str(before_card.get('special'))) or
            ((card_number is not None or (card_number is not None and int(card_number) == 0)) and
             (before_card.get('number') and int(card_number) == int(before_card.get('number'))))
        ):
            # Cards with the same number or symbol as the played card
            cards_valid.append(card)

    """
    Concatenate the lists of playable cards and return the first card.
    In this program, the priority is set as follows: "Same color or same number/symbol" > "Wild, shuffle wild, white wild" > Wild draw 4.
    Wild draw 4 has the lowest priority since it should be played only when there are no cards to play in the hand.
    Wild, shuffle wild, and white wild can be played anytime, so they have lower priority than cards that require the condition "Same color or same number/symbol."
    """
    card_list = cards_valid + cards_wild + cards_wild4
    if len(card_list) > 0:
        return card_list[0]
    else:
        return None

"""
Get a random number

Args:
    num (int):

Returns:
    int:
"""
def random_by_number(num):
    return math.floor(random.random() * num)

"""
Select a color to change to

Returns:
    str:
"""
def select_change_color():
    # In this program, the color to change is selected randomly.
    return ARR_COLOR[random_by_number(len(ARR_COLOR))]

"""
Decide whether to challenge

Returns:
    bool:
"""
def is_challenge():
    # In this program, there is a 1/2 probability of challenging.
    if random_by_number(2) >= 1:
        return True
    else:
        return False

"""
Check for UNO declaration omission by other players

Args:
    number_card_of_player (Any):
"""
def determine_if_execute_pointed_not_say_uno(number_card_of_player):
    global id, uno_declared

    target = None
    # Extract players with only one card in hand
    # Players with more than two cards reset the UNO declaration status
    for k, v in number_card_of_player.items():
        if k == id:
            # Do not process your own ID
            break
        elif v == 1:
            # Player with only one card
            target = k
            break
        elif k in uno_declared:
            # Reset the UNO declaration status for players with two or more cards
            del uno_declared[k]

    if target is None:
        # If there is no player with only one card, abort the process
        return

    # If the extracted player has not declared UNO, point out the omission
    if target not in uno_declared.keys():
        send_event(SocketConst.EMIT.POINTED_NOT_SAY_UNO, {'target': target})
        time.sleep(TIME_DELAY / 1000)

"""
Default function in case individual callback is not specified
"""
def pass_func(err):
    return

"""
Common processing for sending events

Args:
    event (str): Socket communication event name
    data (Any): Data to be sent
    callback (func): Individual processing
"""
def send_event(event, data, callback=pass_func):
    print('Send {} event.'.format(event))
    print('req_data: ', data)

    def after_func(err, res):
        if err:
            print('{} event failed!'.format(event))
            print(err)
            return

        print('Send {} event.'.format(event))
        print('res_data: ', res)
        callback(res)

    sio.emit(event, data, callback=after_func)

"""
Common processing for receiving events

Args:
    event (str): Socket communication event name
    data (Any): Data to be sent
    callback (func): Individual processing
"""
def receive_event(event, data, callback = pass_func):
    print('Receive {} event.'.format(event))
    print('res_data: ', data)

    callback(data)


"""
Establishing socket communication
"""
@sio.on('connect')
def on_connect():
    print('Client connect successfully!')

    if not once_connected:
        if is_test_tool:
            # Connect to the test tool
            if not event_name:
                # No specified event name (when testing the reception of STEP 2 in the development guidelines)
                print('Not found event name')
            elif not event_name in TEST_TOOL_EVENT_DATA:
                # Specified event name, but test data not found is an error
                print('Undefined test data. eventName: ', event_name)
            else:
                # Specified event name and test data found, so send (testing the transmission of STEP 1 in the development guidelines)
                send_event(event_name, TEST_TOOL_EVENT_DATA[event_name])
        else:
            # Connect to the main system
            data = {
                'room_name': room_name,
                'player': player,
            }

            def join_room_callback(*args):
                global once_connected, id
                print('Client join room successfully!')
                once_connected = True
                id = args[0].get('your_id')
                print('My id is {}'.format(id))

            send_event(SocketConst.EMIT.JOIN_ROOM, data, join_room_callback)


"""
Disconnect socket communication
"""
@sio.on('disconnect')
def on_disconnect():
    print('Client disconnect.')
    os._exit(0)


"""
Receiving socket communication
"""
# Player joins the game
@sio.on(SocketConst.EMIT.JOIN_ROOM)
def on_join_room(data_res):
    receive_event(SocketConst.EMIT.JOIN_ROOM, data_res)


# A card is added to the hand
@sio.on(SocketConst.EMIT.RECEIVER_CARD)
def on_reciever_card(data_res):
    receive_event(SocketConst.EMIT.RECEIVER_CARD, data_res)

# Start of the match
@sio.on(SocketConst.EMIT.FIRST_PLAYER)
def on_first_player(data_res):
    receive_event(SocketConst.EMIT.FIRST_PLAYER, data_res)

# Request for the color of the played card
@sio.on(SocketConst.EMIT.COLOR_OF_WILD)
def on_color_of_wild(data_res):
    def color_of_wild_callback(data_res):
        color = select_change_color()
        data = {
            'color_of_wild': color,
        }

        # Execute color change
        send_event(SocketConst.EMIT.COLOR_OF_WILD, data)

    receive_event(SocketConst.EMIT.COLOR_OF_WILD, data_res, color_of_wild_callback)

# The color of the played card has changed
@sio.on(SocketConst.EMIT.UPDATE_COLOR)
def on_update_color(data_res):
    receive_event(SocketConst.EMIT.UPDATE_COLOR, data_res)

# Hand situation changed by Shuffle Wild
@sio.on(SocketConst.EMIT.SHUFFLE_WILD)
def on_shuffle_wild(data_res):
    def shuffle_wild_calback(data_res):
        global uno_declared
        uno_declared = {}
        for k, v in data_res.get('number_card_of_player').items():
            if v == 1:
                # If a player has only one card after shuffling, consider it as saying UNO
                uno_declared[data_res.get('player')] = True
                break
            elif k in uno_declared:
                # If a player receives two or more cards after shuffling, reset the UNO declaration state
                if data_res.get('player') in uno_declared:
                    del uno_declared[k]

    receive_event(SocketConst.EMIT.SHUFFLE_WILD, data_res, shuffle_wild_calback)

# Player's turn
@sio.on(SocketConst.EMIT.NEXT_PLAYER)
def on_next_player(data_res):
    def next_player_calback(data_res):
        determine_if_execute_pointed_not_say_uno(data_res.get('number_card_of_player'))

        cards = data_res.get('card_of_player')

        if (data_res.get('draw_reason') == DrawReason.WILD_DRAW_4):
            # When drawing a Wild Draw 4 card, a challenge can be initiated.
            if is_challenge():
                send_event(SocketConst.EMIT.CHALLENGE, { 'is_challenge': True} )
                return

        if str(data_res.get('must_call_draw_card')) == 'True':
            # When drawing a card is mandatory
            send_event(SocketConst.EMIT.DRAW_CARD, {})
            return

        # Activate special logic
        special_logic_num_random = random_by_number(10)
        if special_logic_num_random == 0:
            send_event(SocketConst.EMIT.SPECIAL_LOGIC, { 'title': SPECIAL_LOGIC_TITLE })

        play_card = select_play_card(cards, data_res.get('card_before'))

        if play_card:
            # When a selected card is available
            print('selected card: {} {}'.format(play_card.get('color'), play_card.get('number') or play_card.get('special')))
            data = {
                'card_play': play_card,
                'yell_uno': len(cards) == 2, # Declare UNO considering the remaining number of cards
            }

            if play_card.get('special') == Special.WILD or play_card.get('special') == Special.WILD_DRAW_4:
                color = select_change_color()
                data['color_of_wild'] = color

            # Execute the event to play the card
            send_event(SocketConst.EMIT.PLAY_CARD, data)
        else:
            # When no card is selected

            # Individual processing when receiving the draw-card event
            def draw_card_callback(res):
                if not res.get('can_play_draw_card'):
                    # If the drawn card cannot be played, end the processing
                    return

                # Subsequent processing when the drawn card can be played
                data = {
                    'is_play_card': True,
                    'yell_uno': len(cards + res.get('draw_card')) == 2, # Declare UNO considering the remaining number of cards
                }

                play_card = res.get('draw_card')[0]
                if play_card.get('special') == Special.WILD or play_card.get('special') == Special.WILD_DRAW_4:
                    color = select_change_color()
                    data['color_of_wild'] = color

                # Execute the event to play the drawn card
                send_event(SocketConst.EMIT.PLAY_DRAW_CARD, data)

            # Execute the event to draw a card
            send_event(SocketConst.EMIT.DRAW_CARD, {}, draw_card_callback)

    receive_event(SocketConst.EMIT.NEXT_PLAYER, data_res, next_player_calback)


# Continue from the previous code snippet

# A card is played
@sio.on(SocketConst.EMIT.PLAY_CARD)
def on_play_card(data_res):
    def play_card_callback(data_res):
        global uno_declared
        # Record UNO declaration if made
        if data_res.get('yell_uno'):
            uno_declared[data_res.get('player')] = data_res.get('yell_uno')

    receive_event(SocketConst.EMIT.PLAY_CARD, data_res, play_card_callback)

# Drew a card from the deck
@sio.on(SocketConst.EMIT.DRAW_CARD)
def on_draw_card(data_res):
    def draw_card_callback(data_res):
        global uno_declared
        # Reset UNO declaration status as cards have increased
        if data_res.get('player') in uno_declared:
            del uno_declared[data_res.get('player')]

    receive_event(SocketConst.EMIT.DRAW_CARD, data_res, draw_card_callback)

# Drew a card from the deck, and the card is played
@sio.on(SocketConst.EMIT.PLAY_DRAW_CARD)
def on_play_draw_card(data_res):
    def play_draw_card_callback(data_res):
        global uno_declared
        # Record UNO declaration if made
        if data_res.get('yell_uno'):
            uno_declared[data_res.get('player')] = data_res.get('yell_uno')

    receive_event(SocketConst.EMIT.PLAY_DRAW_CARD, data_res, play_draw_card_callback)

# Result of a challenge
@sio.on(SocketConst.EMIT.CHALLENGE)
def on_challenge(data_res):
    receive_event(SocketConst.EMIT.CHALLENGE, data_res)

# Publicizing the hand due to a challenge
@sio.on(SocketConst.EMIT.PUBLIC_CARD)
def on_public_card(data_res):
    receive_event(SocketConst.EMIT.PUBLIC_CARD, data_res)

# Pointing out forgetting to say UNO
@sio.on(SocketConst.EMIT.POINTED_NOT_SAY_UNO)
def on_pointed_not_say_uno(data_res):
    receive_event(SocketConst.EMIT.POINTED_NOT_SAY_UNO, data_res)

# The turn is finished
@sio.on(SocketConst.EMIT.FINISH_TURN)
def on_finish_turn(data_res):
    def finish_turn__callback(data_res):
        global uno_declared
        uno_declared = {}

    receive_event(SocketConst.EMIT.FINISH_TURN, data_res, finish_turn__callback)

# The game is finished
@sio.on(SocketConst.EMIT.FINISH_GAME)
def on_finish_game(data_res):
    receive_event(SocketConst.EMIT.FINISH_GAME, data_res)

# Penalty occurred
@sio.on(SocketConst.EMIT.PENALTY)
def on_penalty(data_res):
    def penalty_callback(data_res):
        global uno_declared
        # Reset UNO declaration status as cards have increased
        if data_res.get('player') in uno_declared:
            del uno_declared[data_res.get('player')]

    receive_event(SocketConst.EMIT.PENALTY, data_res, penalty_callback)


def main():
    sio.connect(
        host,
        transports=['websocket'],
    )
    sio.wait()

if __name__ == '__main__':
    main()
