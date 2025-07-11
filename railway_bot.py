"""
Railway Production Bot - Complete Working Version
Based on tested simple_local_bot.py with all your fixes
Includes health server for Railway deployment
"""

import logging
import os
import random
import time
import requests
import re
import threading
import asyncio
from difflib import SequenceMatcher
from aiohttp import web

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_session_id():
    """Generate unique session ID"""
    return f"session_{int(time.time())}_{random.randint(1000, 9999)}"

def determine_rps_winner(choice1, choice2):
    """Determine Rock Paper Scissors winner with Gun/Judo rules"""
    if choice1 == choice2:
        return "tie"
    
    winning_combinations = {
        ("rock", "scissors"): "choice1",
        ("rock", "judo"): "choice1",
        ("paper", "rock"): "choice1", 
        ("paper", "gun"): "choice1",
        ("scissors", "paper"): "choice1",
        ("scissors", "judo"): "choice1",
        ("gun", "rock"): "choice1",
        ("gun", "scissors"): "choice1",
        ("judo", "paper"): "choice1",
        ("judo", "gun"): "choice1"
    }
    
    result = winning_combinations.get((choice1, choice2))
    if result:
        return result
    else:
        return "choice2"

def check_answer_similarity(correct_answer, user_answer):
    """Check if user answer is similar to correct answer"""
    correct_lower = correct_answer.lower().strip()
    user_lower = user_answer.lower().strip()
    
    if correct_lower == user_lower:
        return True
    
    if user_lower in correct_lower or correct_lower in user_lower:
        return True
    
    similarity = SequenceMatcher(None, correct_lower, user_lower).ratio()
    if similarity >= 0.7:
        return True
    
    correct_words = set(re.findall(r'\b\w+\b', correct_lower))
    user_words = set(re.findall(r'\b\w+\b', user_lower))
    
    common_words = correct_words.intersection(user_words)
    if len(common_words) > 0 and len(common_words) >= len(correct_words) * 0.6:
        return True
    
    return False

def create_memory_board():
    """Create a shuffled memory board with 6 pairs"""
    symbols = ['🍎', '🍌', '🍒', '🍇', '🍊', '🥝']
    pairs = symbols * 2
    random.shuffle(pairs)
    
    board = []
    for i in range(3):
        row = []
        for j in range(4):
            row.append({
                'symbol': pairs[i * 4 + j],
                'revealed': False,
                'matched': False
            })
        board.append(row)
    return board

def create_empty_board():
    """Create empty Tic-Tac-Toe board"""
    return [['⬜' for _ in range(3)] for _ in range(3)]

def check_winner(board):
    """Check Tic-Tac-Toe winner"""
    for row in board:
        if row[0] == row[1] == row[2] and row[0] != '⬜':
            return row[0]
    
    for col in range(3):
        if board[0][col] == board[1][col] == board[2][col] and board[0][col] != '⬜':
            return board[0][col]
    
    if board[0][0] == board[1][1] == board[2][2] and board[0][0] != '⬜':
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] and board[0][2] != '⬜':
        return board[0][2]
    
    if all(cell != '⬜' for row in board for cell in row):
        return 'tie'
    
    return None

def format_board(board):
    """Format Tic-Tac-Toe board for display"""
    formatted = ""
    for row in board:
        formatted += " ".join(row) + "\n"
    return formatted.strip()

# Global storage
game_scores = {}
user_data_cache = {}
multiplayer_sessions = {}
active_users = set()

# Game configurations
GAMES = {
    'tictactoe': {'name': '🎯 Tic-Tac-Toe', 'description': 'Classic strategy grid game'},
    'rps': {'name': '🪨 Rock Paper Scissors', 'description': 'With Gun & Judo powers!'},
    'reaction': {'name': '⚡ Reaction Game', 'description': 'Lightning speed reflex test'},
    'qa': {'name': '🧠 Q&A Duel', 'description': 'Question and answer battle'},
    'memory': {'name': '🧩 Memory Match', 'description': 'Concentration tile matching'}
}

class SimpleLocalBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        logger.info("🚀 Starting SIMPLE LOCAL Bot with updated prize messages...")

    def send_message(self, chat_id, text, keyboard=None):
        try:
            data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
            if keyboard:
                data['reply_markup'] = keyboard
            response = requests.post(f"{self.api_url}/sendMessage", json=data, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None

    def edit_message(self, chat_id, message_id, text, keyboard=None):
        try:
            data = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'HTML'}
            if keyboard:
                data['reply_markup'] = keyboard
            response = requests.post(f"{self.api_url}/editMessageText", json=data, timeout=10)
            return response.json()
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return None

    def answer_callback_query(self, callback_query_id, text=""):
        try:
            data = {'callback_query_id': callback_query_id, 'text': text}
            response = requests.post(f"{self.api_url}/answerCallbackQuery", json=data, timeout=5)
            return response.json()
        except Exception as e:
            logger.error(f"Error answering callback: {e}")
            return None

    def register_user(self, user_data):
        user_id = user_data['id']
        user_data_cache[user_id] = user_data
        active_users.add(user_id)
        
        if user_id not in game_scores:
            game_scores[user_id] = {
                'tictactoe': {'wins': 0, 'games': 0},
                'rps': {'wins': 0, 'games': 0},
                'reaction': {'wins': 0, 'games': 0},
                'qa': {'wins': 0, 'games': 0},
                'memory': {'wins': 0, 'games': 0},
                'total_wins': 0,
                'prize_claimed': False,
                'real_prize_claimed': False
            }

    def update_user_game_result(self, user_id, game_type, won, score=None):
        """Update user game result"""
        if user_id not in game_scores:
            self.register_user({'id': user_id, 'first_name': 'Player'})
        
        if game_type not in game_scores[user_id]:
            game_scores[user_id][game_type] = {'wins': 0, 'games': 0}
        
        game_scores[user_id][game_type]['games'] += 1
        if won:
            game_scores[user_id][game_type]['wins'] += 1
            game_scores[user_id]['total_wins'] += 1
        
        if score is not None:
            game_scores[user_id][game_type]['best_score'] = max(
                game_scores[user_id][game_type].get('best_score', 0), score
            )

    def handle_start(self, chat_id, user_data):
        self.register_user(user_data)
        
        start_text = (
            f"🎮 <b>Welcome to the Ultimate Gaming Challenge!</b> 🎮\n\n"
            f"Hey {user_data.get('first_name', 'Player')}! I'm your greatest opponent in life. Are you ready to lose?\n\n"
            f"There are 5 exciting games below for you to choose:\n\n"
            f"🎯 <b>Tic-Tac-Toe</b> - Classic strategy grid game\n"
            f"🪨 <b>Rock Paper Scissors</b> - With Gun & Judo powers!\n"
            f"⚡ <b>Reaction Game</b> - Lightning speed reflex test\n"
            f"🧠 <b>Q&A Duel</b> - Question and answer battle\n"
            f"🧩 <b>Memory Match</b> - Concentration tile matching\n\n"
            f"🏆 <b>Special Prize Alert!</b>\n"
            f"Beat me 3 times in any of these games (can be the same games) to unlock a special surprise! 🎁\n\n"
            f"Ready to get destroyed? Let's play! 😈"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Let\'s Play!', 'callback_data': 'show_games'}]
            ]
        }
        
        self.send_message(chat_id, start_text, keyboard)

    def show_game_menu(self, chat_id, message_id, user_id):
        self.register_user({'id': user_id, 'first_name': 'Player'})
        
        menu_text = (
            "🎮 <b>Choose Your Battle!</b> 🎮\n\n"
            "Select a game below to versus your opponent:\n\n"
            "🎯 Tic-Tac-Toe (vs Player)\n"
            "🪨 Rock Paper Scissors (vs Player)\n"
            "⚡ Reaction Game (vs Player)\n"
            "🧠 Q&A Duel (vs Player)\n"
            "🧩 Memory Match (vs Player)\n\n"
            "All games are multiplayer! Challenge other players!"
        )
        
        keyboard_buttons = [
            [{'text': '🎯 Tic-Tac-Toe (vs Player)', 'callback_data': 'invite_tictactoe'}],
            [{'text': '🪨 Rock Paper Scissors (vs Player)', 'callback_data': 'invite_rps'}],
            [{'text': '⚡ Reaction Game (vs Player)', 'callback_data': 'invite_reaction'}],
            [{'text': '🧠 Q&A Duel (vs Player)', 'callback_data': 'invite_qa'}],
            [{'text': '🧩 Memory Match (vs Player)', 'callback_data': 'invite_memory'}],
            [{'text': '🔍 Find Active Games', 'callback_data': 'find_games'}],
            [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
        ]
        
        # Check for prize eligibility
        total_wins = game_scores.get(user_id, {}).get('total_wins', 0)
        if total_wins >= 3:
            if game_scores.get(user_id, {}).get('prize_claimed', False):
                keyboard_buttons.insert(-1, [{'text': '🎁 View Prize Message', 'callback_data': 'view_prize'}])
            else:
                keyboard_buttons.insert(-1, [{'text': '🎁 Claim Your Prize!', 'callback_data': 'reveal_prize'}])
        
        keyboard = {'inline_keyboard': keyboard_buttons}
        
        if message_id:
            self.edit_message(chat_id, message_id, menu_text, keyboard)
        else:
            self.send_message(chat_id, menu_text, keyboard)



    def handle_prize_reveal(self, chat_id, message_id, user_id):
        """Show UPDATED fake prize message"""
        self.register_user({'id': user_id, 'first_name': 'Player'})
        game_scores[user_id]['prize_claimed'] = True
        
        # UPDATED fake prize message
        prize_text = (
            "🎁 <b>CONGRATULATIONS!</b> 🎁\n\n"
            "🤡🤡🤡 DUMBOOOOO YOU REALLY THINK U WONNNN??? 🤡🤡🤡"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎁 Get Real Prize', 'callback_data': 'real_prize'}],
                [{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]
            ]
        }
        
        self.edit_message(chat_id, message_id, prize_text, keyboard)

    def handle_real_prize_reveal(self, chat_id, message_id, user_id):
        """Show UPDATED real prize message"""
        self.register_user({'id': user_id, 'first_name': 'Player'})
        game_scores[user_id]['real_prize_claimed'] = True
        
        # UPDATED real prize message with your refinements
        real_prize_text = (
            "🎉 You win!\n"
            "And here's your real prize:\n\n"
            "Miss Overthinker. Miss Judo. Miss Taekwondo.\n"
            "Look at you now... made it through uni and still standing strong 😏\n\n"
            "Uni? ✋\n"
            "Grad trip? Slayed 🐏\n"
            "Now it's the \"working adult\" era... or wait, don't want to work right? Just want to slack, eat good food, travel the world, and chill in aesthetic cafés every day 😎 (Haiyaaa... ngl, who don want?)\n\n"
            "And civil engineer? Lol, screw that 🙅‍♀️\n"
            "You survived it... no need to build bridges when you're out here building your life instead.\n\n"
            "But real talk... you made it through all the chaos. The late nights, the mental spirals, the group project dramas, the \"what am I even doing 🤷‍♀️\" moments. You pulled through, even when everything felt like a mess. That says a lot about you.\n\n"
            "So yeah, even if life feels like one of those dreamy moodboards... pretty, but kind of all over the place... just know it's okay, girl. You don't need a perfect plan yet. Maybe you're not supposed to follow some fixed path anyway. Maybe you're meant to make your own, slowly, intentionally... one that feels like you.\n\n"
            "Take your time. Rest a little. Dream a lot. Trust your gut. You've already shown you're stronger and more capable than you realise 🐣\n\n"
            "And Coreen being Coreen...\n"
            "Of course you crushed it lah 😏\n\n"
            "Fun fact: that day when we met, I accidentally asked about your ermhem height… which is why I sent you that voice message HOHO 😅\n\n"
            "I actually pondered for a bit like, \"oh sh*t… did Coreen get offended?\"\n"
            "Especially after remembering someone's bio clearly said: 'She is small. Don't ask about her _____.'\n\n"
            "But honestly… who cares whether you're small? Someone already in Judo, Taekwondo… what else?\n"
            "Need people give you chance isit? 😏\n\n"
            "No surprise. But still proud of you! ☺️\n"
            "Go do great things, and cause a little chaos while you're at it 💥\n\n"
            "🎈🎁🎊 AMAZING WORK 🎊🎁🎈\n\n"
            "And maybe just one more thing since I blabla so much alr.\n\n"
            "Remember the very first time when we started talking, I said I wanted to take up the challenge to get to know you for who u are?🙈\n"
            "I genuinely meant it.\n\n"
            "Okay maybe I have asked some dumb or random things before (and possibly accidentally gave off mixed signal along the way...)\n"
            "But here's the truth... I genuinely want to pursue you. Gently, patiently, and with intention. Nothing stressful, nothing rushed. Just something that feels real and kind, even while you are figuring out your own path.\n\n"
            "No pressure if you just want to silently judge me 😏\n"
            "That's what girls do best, isn't it? HAHA\n\n"
            "Also… didn't someone once say she likes to \"keeps things to herself\"? 😏\n"
            "Dangerous girl alert. Must be hiding all kinds of secrets huh? 👀\n\n"
            "You know what... I dare you to ask me anything.\n"
            "Deep, random, weird or even embarassing qnss\n"
            "I'll answer honestly…\n"
            "unless it's \"why does matcha taste like grass?\" because that's just slander 😤YOU NOOB"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]
            ]
        }
        
        self.edit_message(chat_id, message_id, real_prize_text, keyboard)

    def create_multiplayer_invitation(self, chat_id, message_id, user_id, user_data, game_type):
        """Create multiplayer game invitation"""
        self.register_user(user_data)
        session_id = generate_session_id()
        
        multiplayer_sessions[session_id] = {
            'game_type': game_type,
            'host_id': user_id,
            'host_name': user_data.get('first_name', 'Player'),
            'players': [user_id],
            'status': 'waiting',
            'created_at': time.time()
        }
        
        game_name = GAMES.get(game_type, {}).get('name', 'Game')
        
        invitation_text = (
            f"🎮 <b>Multiplayer Game Created!</b> 🎮\n\n"
            f"Game: {game_name}\n"
            f"Host: {user_data.get('first_name', 'Player')}\n"
            f"Status: Waiting for opponent...\n\n"
            f"Share this message with anyone who might want to play!\n"
            f"Game ID: <code>{session_id}</code>"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '⏳ Waiting for player...', 'callback_data': 'noop'}],
                [{'text': '❌ Cancel Game', 'callback_data': f'cancel_{session_id}'}],
                [{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]
            ]
        }
        
        self.edit_message(chat_id, message_id, invitation_text, keyboard)
        
        # Send notification to other active users
        self.broadcast_game_notification(user_id, user_data.get('first_name', 'Player'), game_name, session_id)

    def broadcast_game_notification(self, host_id, host_username, game_name, session_id):
        """Send notification to other active users with DIRECT JOIN BUTTON"""
        notification_text = (
            f"🎮 <b>New Game Available!</b> 🎮\n\n"
            f"Player: {host_username}\n"
            f"Game: {game_name}\n\n"
            f"Want to play? Join now!"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Join Game', 'callback_data': f'join_{session_id}'}],
                [{'text': '🔍 Find Active Games', 'callback_data': 'find_games'}]
            ]
        }
        
        for user_id in active_users:
            if user_id != host_id:
                try:
                    self.send_message(user_id, notification_text, keyboard)
                except Exception as e:
                    logger.error(f"Error sending notification to {user_id}: {e}")
                    active_users.discard(user_id)

    def show_active_games(self, chat_id, message_id):
        """Show active games waiting for players"""
        current_time = time.time()
        active_games = []
        
        for session_id, session in list(multiplayer_sessions.items()):
            if current_time - session.get('created_at', 0) > 600:
                del multiplayer_sessions[session_id]
                continue
            
            if session.get('status') == 'waiting':
                active_games.append((session_id, session))
        
        if not active_games:
            no_games_text = (
                "🔍 <b>No Active Games</b> 🔍\n\n"
                "There are no games waiting for players right now.\n\n"
                "Create your own game to get started!"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Create New Game', 'callback_data': 'show_games'}]
                ]
            }
            
            self.edit_message(chat_id, message_id, no_games_text, keyboard)
            return
        
        games_text = "🔍 <b>Active Games</b> 🔍\n\n"
        keyboard_buttons = []
        
        for session_id, session in active_games[:5]:
            game_name = GAMES.get(session['game_type'], {}).get('name', 'Game')
            host_name = session.get('host_name', 'Player')
            
            games_text += f"• {game_name} by {host_name}\n"
            keyboard_buttons.append([{
                'text': f'🎮 Join {game_name}',
                'callback_data': f'join_{session_id}'
            }])
        
        keyboard_buttons.append([{'text': '🎮 Create New Game', 'callback_data': 'show_games'}])
        keyboard = {'inline_keyboard': keyboard_buttons}
        
        self.edit_message(chat_id, message_id, games_text, keyboard)

    def handle_invite_acceptance(self, chat_id, message_id, user_id, user_data, session_id):
        """Handle when someone accepts a multiplayer invitation"""
        self.register_user(user_data)
        
        if session_id not in multiplayer_sessions:
            self.edit_message(chat_id, message_id, "❌ Game session expired or no longer available.", {
                'inline_keyboard': [[{'text': '🎮 Find Other Games', 'callback_data': 'find_games'}]]
            })
            return
        
        session = multiplayer_sessions[session_id]
        
        if user_id == session['host_id']:
            self.edit_message(chat_id, message_id, "❌ You can't join your own game!", {
                'inline_keyboard': [[{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]]
            })
            return
        
        if len(session['players']) >= 2:
            self.edit_message(chat_id, message_id, "❌ Game is already full!", {
                'inline_keyboard': [[{'text': '🔍 Find Other Games', 'callback_data': 'find_games'}]]
            })
            return
        
        session['players'].append(user_id)
        session['status'] = 'active'
        session['player_names'] = {
            session['host_id']: session['host_name'],
            user_id: user_data.get('first_name', 'Player')
        }
        
        host_notification = f"🎮 {user_data.get('first_name', 'Player')} joined your game! Starting now..."
        self.send_message(session['host_id'], host_notification)
        
        self.start_multiplayer_game(chat_id, message_id, user_id, session_id)

    def show_scoreboard(self, chat_id, message_id, user_id):
        """Show comprehensive scoreboard"""
        self.register_user({'id': user_id, 'first_name': 'Player'})
        
        user_stats = game_scores.get(user_id, {})
        total_wins = user_stats.get('total_wins', 0)
        total_games = sum(game_data.get("games", 0) for game_data in user_stats.values() if isinstance(game_data, dict))
        
        win_rate = (total_wins / total_games * 100) if total_games > 0 else 0
        
        if total_wins == 0:
            tier = "🎯 Ready to Play"
        elif total_wins < 3:
            tier = "🌟 Getting Started"
        elif total_wins < 10:
            tier = "⭐ Rising Star"
        elif total_wins < 25:
            tier = "🏆 Skilled Player"
        else:
            tier = "👑 Legend Status"
        
        scoreboard_text = (
            f"🏆 <b>Personal Statistics</b> 🏆\n\n"
            f"👤 <b>Player Profile</b>\n"
            f"Total Wins: {total_wins}\n"
            f"Games Played: {total_games}\n"
            f"Win Rate: {win_rate:.1f}%\n"
            f"Tier: {tier}\n\n"
            f"🎮 <b>Game Breakdown</b>\n"
        )
        
        for game_key, game_info in GAMES.items():
            game_stats = user_stats.get(game_key, {'wins': 0, 'games': 0})
            wins = game_stats.get('wins', 0)
            games = game_stats.get('games', 0)
            game_win_rate = (wins / games * 100) if games > 0 else 0
            
            scoreboard_text += f"{game_info['name']}: {wins}W/{games}G ({game_win_rate:.0f}%)\n"
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Play Games', 'callback_data': 'show_games'}]
            ]
        }
        
        self.edit_message(chat_id, message_id, scoreboard_text, keyboard)

    def start_multiplayer_game(self, chat_id, message_id, user_id, session_id):
        """Start a multiplayer game"""
        if session_id not in multiplayer_sessions:
            self.edit_message(chat_id, message_id, "❌ Game session expired.", None)
            return
        
        session = multiplayer_sessions[session_id]
        game_type = session["game_type"]
        
        if game_type == "tictactoe":
            self.start_tictactoe_game(session_id)
            self.update_tictactoe_display(session_id)
        elif game_type == "rps":
            self.start_rps_game(session_id)
            self.update_rps_display(session_id)
        elif game_type == "reaction":
            self.start_reaction_game(session_id)
            self.update_reaction_display(session_id)
        elif game_type == "memory":
            self.start_memory_game(session_id)
            self.update_memory_display(session_id)
        elif game_type == "qa":
            self.start_qa_game(session_id)
            self.update_qa_display(session_id)
        else:
            self.edit_message(chat_id, message_id, f"🎮 {GAMES.get(game_type, {}).get('name', 'Game')} implementation coming soon!", {
                'inline_keyboard': [[{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]]
            })

    def start_tictactoe_game(self, session_id):
        """Initialize Tic-Tac-Toe game"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        player1_id, player2_id = session['players']
        
        session['game_state'] = {
            'board': create_empty_board(),
            'current_turn': 0,
            'player_symbols': {player1_id: '❌', player2_id: '⭕'},
            'session_id': session_id
        }

    def update_tictactoe_display(self, session_id):
        """Update Tic-Tac-Toe display for both players"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        current_player_id = session['players'][game_state['current_turn']]
        other_player_id = session['players'][1 - game_state['current_turn']]
        
        board_text = format_board(game_state['board'])
        
        current_player_text = (
            f"🎯 <b>Multiplayer Tic-Tac-Toe</b> 🎯\n\n"
            f"{board_text}\n\n"
            f"You are {game_state['player_symbols'][current_player_id]}\n"
            f"🎮 <b>Current turn: Your turn</b>\n\n"
            "Choose your move:"
        )
        
        other_player_text = (
            f"🎯 <b>Multiplayer Tic-Tac-Toe</b> 🎯\n\n"
            f"{board_text}\n\n"
            f"You are {game_state['player_symbols'][other_player_id]}\n"
            f"⏳ <b>Current turn: Opponent's</b>\n\n"
            "Waiting for opponent's move..."
        )
        
        keyboard_buttons = []
        for i in range(3):
            row_buttons = []
            for j in range(3):
                if game_state['board'][i][j] == '⬜':
                    row_buttons.append({
                        'text': '⬜',
                        'callback_data': f'ttt_{i}_{j}_{session_id}'
                    })
                else:
                    row_buttons.append({
                        'text': game_state['board'][i][j],
                        'callback_data': 'noop'
                    })
            keyboard_buttons.append(row_buttons)
        
        keyboard_buttons.append([{'text': '🎮 Quit Game', 'callback_data': 'show_games'}])
        
        current_player_keyboard = {'inline_keyboard': keyboard_buttons}
        other_player_keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
            ]
        }
        
        try:
            self.send_message(current_player_id, current_player_text, current_player_keyboard)
            self.send_message(other_player_id, other_player_text, other_player_keyboard)
        except Exception as e:
            logger.error(f"Error updating Tic-Tac-Toe display: {e}")

    def handle_tictactoe_move(self, session_id, user_id, position):
        """Handle Tic-Tac-Toe move with INSTANT response and winner checking"""
        logger.info(f"Handling Tic-Tac-Toe move: session={session_id}, user={user_id}, position={position}")
        
        if session_id not in multiplayer_sessions:
            logger.warning(f"Session {session_id} not found")
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        current_player_id = session['players'][game_state['current_turn']]
        if user_id != current_player_id:
            logger.warning(f"User {user_id} tried to move but it's {current_player_id}'s turn")
            return
        
        try:
            row, col = map(int, position.split('_'))
            logger.info(f"Move position: row={row}, col={col}")
        except Exception as e:
            logger.error(f"Error parsing position {position}: {e}")
            return
        
        if row < 0 or row > 2 or col < 0 or col > 2:
            logger.warning(f"Invalid position: {row}, {col}")
            return
        
        if game_state['board'][row][col] != '⬜':
            logger.warning(f"Position {row},{col} already occupied")
            return
        
        player_symbol = game_state['player_symbols'][user_id]
        game_state['board'][row][col] = player_symbol
        logger.info(f"Move made: {player_symbol} at {row},{col}")
        
        winner = check_winner(game_state['board'])
        
        if winner:
            logger.info(f"Game ended with winner: {winner}")
            self.end_tictactoe_game(session_id, winner)
        else:
            game_state['current_turn'] = 1 - game_state['current_turn']
            logger.info(f"Turn switched to player {game_state['current_turn']}")
            self.update_tictactoe_display(session_id)

    def end_tictactoe_game(self, session_id, winner):
        """End Tic-Tac-Toe game and show results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        board_text = format_board(game_state['board'])
        
        if winner == 'tie':
            result_text = (
                f"🎯 <b>Multiplayer Tic-Tac-Toe - GAME OVER</b> 🎯\n\n"
                f"{board_text}\n\n"
                f"🤝 <b>IT'S A TIE!</b> 🤝\n\n"
                f"Great game! Both players showed skill."
            )
            
            for player_id in session['players']:
                self.update_user_game_result(player_id, 'tictactoe', False)
        else:
            winner_id = None
            for pid, symbol in game_state['player_symbols'].items():
                if symbol == winner:
                    winner_id = pid
                    break
            
            loser_id = player2_id if winner_id == player1_id else player1_id
            
            winner_text = (
                f"🎯 <b>Multiplayer Tic-Tac-Toe - GAME OVER</b> 🎯\n\n"
                f"{board_text}\n\n"
                f"🎉 <b>YOU WON!</b> 🎉\n\n"
                f"Congratulations! You defeated your opponent with {winner}!"
            )
            
            loser_text = (
                f"🎯 <b>Multiplayer Tic-Tac-Toe - GAME OVER</b> 🎯\n\n"
                f"{board_text}\n\n"
                f"😔 <b>YOU LOST!</b> 😔\n\n"
                f"Your opponent won with {winner}. Better luck next time!"
            )
            
            self.update_user_game_result(winner_id, 'tictactoe', True)
            self.update_user_game_result(loser_id, 'tictactoe', False)
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Play Other Games', 'callback_data': 'show_games'}],
                    [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
                ]
            }
            
            self.send_message(winner_id, winner_text, keyboard)
            self.send_message(loser_id, loser_text, keyboard)
            
            del multiplayer_sessions[session_id]
            
            self.check_prize_eligibility(winner_id)
            return
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Play Other Games', 'callback_data': 'show_games'}],
                [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
            ]
        }
        
        for player_id in session['players']:
            self.send_message(player_id, result_text, keyboard)
        
        del multiplayer_sessions[session_id]

    def start_rps_game(self, session_id):
        """Initialize Rock Paper Scissors game"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        player1_id, player2_id = session['players']
        
        session['game_state'] = {
            'round': 1,
            'max_rounds': 3,
            'scores': {player1_id: 0, player2_id: 0},
            'choices': {},
            'session_id': session_id,
            'waiting_for': [player1_id, player2_id]
        }

    def update_rps_display(self, session_id):
        """Update Rock Paper Scissors display for both players"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        # Check if game should end (someone has 2 wins)
        if max(game_state['scores'].values()) >= 2:
            self.end_rps_game(session_id)
            return
        
        current_round = game_state['round']
        player1_score = game_state['scores'][player1_id]
        player2_score = game_state['scores'][player2_id]
        
        instructions_text = (
            "📋 <b>Game Rules:</b>\n"
            "🪨 Rock beats Scissors & Judo\n"
            "📄 Paper beats Rock & Gun\n"
            "✂️ Scissors beats Paper & Judo\n"
            "🔫 Gun beats Rock & Scissors\n"
            "🥋 Judo beats Paper & Gun\n\n"
        )
        
        for player_id in [player1_id, player2_id]:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            if player_id in game_state['choices']:
                # Player has made choice, waiting for opponent
                choice_emojis = {
                    'rock': '🪨', 'paper': '📄', 'scissors': '✂️', 
                    'gun': '🔫', 'judo': '🥋'
                }
                player_choice_emoji = choice_emojis.get(game_state['choices'][player_id], '❓')
                
                waiting_text = (
                    f"🪨 <b>Rock Paper Scissors - Round {current_round}</b> 📄\n\n"
                    f"{instructions_text}"
                    f"Your Score: {player_score} | Opponent: {opponent_score}\n"
                    f"Best of 3 rounds - First to 2 wins!\n\n"
                    f"✅ <b>Your choice: {player_choice_emoji}</b>\n"
                    f"⏳ Waiting for opponent's choice..."
                )
                
                keyboard = {
                    'inline_keyboard': [
                        [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                    ]
                }
            else:
                # Player needs to make choice
                choice_text = (
                    f"🪨 <b>Rock Paper Scissors - Round {current_round}</b> 📄\n\n"
                    f"{instructions_text}"
                    f"Your Score: {player_score} | Opponent: {opponent_score}\n"
                    f"Best of 3 rounds - First to 2 wins!\n\n"
                    f"🎮 <b>Make your choice:</b>"
                )
                
                keyboard = {
                    'inline_keyboard': [
                        [
                            {'text': '🪨 Rock', 'callback_data': f'rps_rock_{session_id}'},
                            {'text': '📄 Paper', 'callback_data': f'rps_paper_{session_id}'}
                        ],
                        [
                            {'text': '✂️ Scissors', 'callback_data': f'rps_scissors_{session_id}'},
                            {'text': '🔫 Gun', 'callback_data': f'rps_gun_{session_id}'}
                        ],
                        [
                            {'text': '🥋 Judo', 'callback_data': f'rps_judo_{session_id}'}
                        ],
                        [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                    ]
                }
            
            try:
                if player_id in game_state['choices']:
                    self.send_message(player_id, waiting_text, keyboard)
                else:
                    self.send_message(player_id, choice_text, keyboard)
            except Exception as e:
                logger.error(f"Error updating RPS display for player {player_id}: {e}")

    def handle_rps_choice(self, session_id, user_id, choice):
        """Handle Rock Paper Scissors choice"""
        logger.info(f"RPS choice: session={session_id}, user={user_id}, choice={choice}")
        
        if session_id not in multiplayer_sessions:
            logger.warning(f"RPS session {session_id} not found")
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        if user_id not in session['players']:
            logger.warning(f"User {user_id} not in RPS game")
            return
        
        if user_id in game_state['choices']:
            logger.warning(f"User {user_id} already made choice")
            return
        
        # Check if game is already being processed (prevent double processing)
        if game_state.get('processing', False):
            logger.warning(f"Game {session_id} already being processed")
            return
        
        game_state['choices'][user_id] = choice
        logger.info(f"Choice recorded: {choice}")
        
        # Check if both players have chosen
        if len(game_state['choices']) == 2:
            # Mark as processing to prevent double execution
            game_state['processing'] = True
            self.resolve_rps_round(session_id)
        else:
            # Update display to show waiting state
            self.update_rps_display(session_id)

    def resolve_rps_round(self, session_id):
        """Resolve Rock Paper Scissors round"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        choice1 = game_state['choices'][player1_id]
        choice2 = game_state['choices'][player2_id]
        
        result = determine_rps_winner(choice1, choice2)
        
        choice_emojis = {
            'rock': '🪨', 'paper': '📄', 'scissors': '✂️', 
            'gun': '🔫', 'judo': '🥋'
        }
        
        choice1_emoji = choice_emojis[choice1]
        choice2_emoji = choice_emojis[choice2]
        
        if result == "tie":
            round_result = "🤝 <b>TIE!</b>"
        elif result == "choice1":
            game_state['scores'][player1_id] += 1
            round_result = f"🎉 <b>{choice1_emoji} {choice1.title()} beats {choice2_emoji} {choice2.title()}!</b>"
        else:
            game_state['scores'][player2_id] += 1
            round_result = f"🎉 <b>{choice2_emoji} {choice2.title()} beats {choice1_emoji} {choice1.title()}!</b>"
        
        # Show round results to both players (prevent double messages)
        current_round = game_state['round']
        if not game_state.get('results_shown', False):
            for player_id in session['players']:
                opponent_id = player2_id if player_id == player1_id else player1_id
                player_score = game_state['scores'][player_id]
                opponent_score = game_state['scores'][opponent_id]
                
                result_text = (
                    f"🪨 <b>Round {current_round} Results</b> 📄\n\n"
                    f"You: {choice_emojis[game_state['choices'][player_id]]} {game_state['choices'][player_id].title()}\n"
                    f"Opponent: {choice_emojis[game_state['choices'][opponent_id]]} {game_state['choices'][opponent_id].title()}\n\n"
                    f"{round_result}\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
                
                keyboard = {
                    'inline_keyboard': [
                        [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                    ]
                }
                
                self.send_message(player_id, result_text, keyboard)
            
            game_state['results_shown'] = True
        
        # Clear choices, processing flag, and results flag
        game_state['choices'] = {}
        game_state['processing'] = False
        game_state['results_shown'] = False
        
        # Check if game should end
        if max(game_state['scores'].values()) >= 2:
            # Small delay then end game
            import threading
            threading.Timer(2.0, lambda: self.end_rps_game(session_id)).start()
        else:
            # Increment round for next round and start it
            game_state['round'] += 1
            import threading  
            threading.Timer(2.0, lambda: self.update_rps_display(session_id)).start()



    def end_rps_game(self, session_id):
        """End Rock Paper Scissors game and show results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        player1_score = game_state['scores'][player1_id]
        player2_score = game_state['scores'][player2_id]
        
        if player1_score > player2_score:
            winner_id = player1_id
            loser_id = player2_id
        else:
            winner_id = player2_id
            loser_id = player1_id
        
        # Update stats
        self.update_user_game_result(winner_id, 'rps', True)
        self.update_user_game_result(loser_id, 'rps', False)
        
        # Send personalized results
        winner_text = (
            f"🪨 <b>Rock Paper Scissors - GAME OVER</b> 📄\n\n"
            f"🎉 <b>YOU WON!</b> 🎉\n\n"
            f"Final Score: You {game_state['scores'][winner_id]} - {game_state['scores'][loser_id]} Opponent\n\n"
            f"Excellent strategy! You mastered the Gun & Judo powers!"
        )
        
        loser_text = (
            f"🪨 <b>Rock Paper Scissors - GAME OVER</b> 📄\n\n"
            f"😔 <b>YOU LOST!</b> 😔\n\n"
            f"Final Score: You {game_state['scores'][loser_id]} - {game_state['scores'][winner_id]} Opponent\n\n"
            f"Good game! Practice with Gun & Judo for better results!"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Play Other Games', 'callback_data': 'show_games'}],
                [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
            ]
        }
        
        self.send_message(winner_id, winner_text, keyboard)
        self.send_message(loser_id, loser_text, keyboard)
        
        del multiplayer_sessions[session_id]
        self.check_prize_eligibility(winner_id)

    def start_reaction_game(self, session_id):
        """Initialize Reaction Game"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        player1_id, player2_id = session['players']
        
        session['game_state'] = {
            'round': 1,
            'max_rounds': 5,
            'scores': {player1_id: 0, player2_id: 0},
            'current_phase': 'waiting_ready',
            'ready_players': set(),
            'round_start_time': None,
            'round_active': False,
            'session_id': session_id,
            'green_count': 0,
            'max_green_rounds': 3
        }

    def update_reaction_display(self, session_id):
        """Update Reaction Game display for both players"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        current_round = game_state['round']
        
        for player_id in [player1_id, player2_id]:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            if game_state['current_phase'] == 'waiting_ready':
                ready_text = (
                    f"⚡ <b>Reaction Game - Round {current_round}/5</b> ⚡\n\n"
                    f"📋 <b>Rules:</b>\n"
                    f"• Wait for GREEN circle (🟢)\n"
                    f"• Tap as fast as possible when you see it\n"
                    f"• DON'T tap on red (🔴) or yellow (🟡)\n"
                    f"• Score points based on reaction time!\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"🎯 <b>Get ready for Round {current_round}!</b>"
                )
                
                if player_id in game_state['ready_players']:
                    keyboard = {
                        'inline_keyboard': [
                            [{'text': '✅ Ready! Waiting for opponent...', 'callback_data': 'noop'}],
                            [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                        ]
                    }
                else:
                    keyboard = {
                        'inline_keyboard': [
                            [{'text': '🚀 I\'m Ready!', 'callback_data': f'reaction_ready_{session_id}'}],
                            [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                        ]
                    }
                
                self.send_message(player_id, ready_text, keyboard)

    def handle_reaction_ready(self, session_id, user_id):
        """Handle player ready for reaction round"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        if user_id not in session['players']:
            return
        
        game_state['ready_players'].add(user_id)
        
        # Check if both players are ready
        if len(game_state['ready_players']) == 2:
            # Both players ready - send countdown message
            countdown_text = (
                f"🚀 <b>Both players are ready!</b> 🚀\n\n"
                f"Get ready to start Round {game_state['round']}!\n\n"
                f"⏰ <b>Starting in 10 seconds...</b>"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
            
            # Send countdown to both players
            for player_id in session['players']:
                self.send_message(player_id, countdown_text, keyboard)
            
            # Start countdown timer
            import threading
            threading.Timer(10.0, lambda: self.start_reaction_round(session_id)).start()
        else:
            # Only one player ready - send waiting message
            ready_player = user_id
            waiting_player = player2_id if user_id == player1_id else player1_id
            
            # Send confirmation to ready player
            self.send_message(ready_player, "✅ You are ready! Waiting for opponent...")
            
            # Send notification to waiting player
            waiting_text = (
                f"⏳ <b>Waiting for you to get ready!</b>\n\n"
                f"Your opponent is ready for Round {game_state['round']}.\n"
                f"Click Ready when you're prepared!"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '✅ Ready!', 'callback_data': f'reaction_ready_{session_id}'}],
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
            
            self.send_message(waiting_player, waiting_text, keyboard)

    def start_reaction_round(self, session_id):
        """Start reaction round with random delay"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        # Prevent duplicate execution
        if game_state.get('round_starting', False):
            return
        game_state['round_starting'] = True
        
        # Show "Get Ready" message to both players
        for player_id in session['players']:
            ready_text = (
                f"⚡ <b>Round {game_state['round']}/5</b> ⚡\n\n"
                f"🔴 <b>GET READY...</b>\n\n"
                f"Wait for the GREEN circle!"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
            
            self.send_message(player_id, ready_text, keyboard)
        
        # Random delay between 2.5-3.5 seconds, then show green or fake-out
        import threading
        delay = random.uniform(2.5, 3.5)
        threading.Timer(delay, lambda: self.show_reaction_target(session_id)).start()

    def show_reaction_target(self, session_id):
        """Show reaction target (green or fake-out)"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        # Prevent duplicate execution
        if game_state.get('target_showing', False):
            return
        game_state['target_showing'] = True
        game_state['round_starting'] = False  # Clear round starting flag
        
        # Decide if this is green round or fake-out
        is_green = game_state['green_count'] < game_state['max_green_rounds']
        
        if is_green and random.random() < 0.7:  # 70% chance for green if we haven't hit max
            # GREEN - Real reaction test
            game_state['round_active'] = True
            game_state['round_start_time'] = time.time()
            game_state['green_count'] += 1
            game_state['round_taps'] = {}  # Track both players' taps
            
            target_text = (
                f"⚡ <b>Round {game_state['round']}/5</b> ⚡\n\n"
                f"🟢 <b>TAP NOW!</b> 🟢\n\n"
                f"Both players can score points!"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🟢 TAP!', 'callback_data': f'reaction_tap_{session_id}'}],
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
        else:
            # FAKE-OUT - Red or Yellow
            fake_color = random.choice(['🔴', '🟡'])
            color_name = "RED" if fake_color == '🔴' else "YELLOW"
            
            target_text = (
                f"⚡ <b>Round {game_state['round']}/5</b> ⚡\n\n"
                f"{fake_color} <b>{color_name} - DON'T TAP!</b> {fake_color}\n\n"
                f"Wait for GREEN!"
            )
            
            # Clickable button for fake-outs - players get penalized if they click
            keyboard = {
                'inline_keyboard': [
                    [{'text': f'{fake_color} TAP', 'callback_data': f'reaction_wrong_{session_id}'}],
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
        
        for player_id in session['players']:
            self.send_message(player_id, target_text, keyboard)
        
        if not is_green:
            # Auto-continue fake-out rounds after 3 seconds with success message (only if no wrong taps)
            import threading
            threading.Timer(3.0, lambda: self.handle_fake_out_auto_continue(session_id)).start()
        else:
            # For green rounds, auto-end after 4.0 seconds to give both players time
            import threading
            threading.Timer(4.0, lambda: self.check_reaction_timeout(session_id)).start()

    def handle_reaction_tap(self, session_id, user_id):
        """Handle reaction tap"""
        logger.info(f"DETAILED DEBUG - handle_reaction_tap called for user {user_id} in session {session_id}")
        
        if session_id not in multiplayer_sessions:
            logger.error(f"FAILURE: Session {session_id} not found for user {user_id}")
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        logger.info(f"DEBUG - Session found, players: {session['players']}")
        
        if not game_state.get('round_active', False):
            logger.error(f"FAILURE: Round not active for session {session_id}, user {user_id}. round_active={game_state.get('round_active')}")
            return
        
        if user_id not in session['players']:
            logger.error(f"FAILURE: User {user_id} not in session {session_id} players {session['players']}")
            return
        
        # Check if player already tapped this round
        current_round_taps = game_state.get('round_taps', {})
        logger.info(f"DEBUG - Current round_taps: {current_round_taps}")
        if user_id in current_round_taps:
            logger.error(f"FAILURE: User {user_id} already tapped this round. round_taps={current_round_taps}")
            return
        
        # Calculate reaction time with network latency compensation
        start_time = game_state.get('round_start_time', 0)
        tap_time = time.time()
        raw_reaction_time = tap_time - start_time
        
        # Check if this is the first or second tap to determine relative timing
        current_round_taps = game_state.get('round_taps', {})
        if len(current_round_taps) == 0:
            # First player to tap - use raw time
            reaction_time = raw_reaction_time
            game_state['first_tap_time'] = tap_time
        else:
            # Second player to tap - calculate relative to first tap
            first_tap_time = game_state.get('first_tap_time', tap_time)
            time_difference = tap_time - first_tap_time
            
            # If second player tapped within 0.5 seconds of first, they likely tapped faster
            # Adjust their time to be more fair
            if time_difference < 0.5:
                # Give them a bonus for quick follow-up (likely they tapped simultaneously)
                reaction_time = raw_reaction_time - (0.5 - time_difference)
            else:
                reaction_time = raw_reaction_time
        
        # Ensure minimum reaction time of 0.1 seconds
        reaction_time = max(0.1, reaction_time)
        
        logger.info(f"DEBUG - Player {user_id} timing: start={start_time}, tap={tap_time}, raw={raw_reaction_time:.3f}, adjusted={reaction_time:.3f}")
        
        # Award points based on precise reaction time - same calculation for all players
        # Using continuous formula to ensure exact timing fairness
        if reaction_time <= 0.5:
            points = 100
        elif reaction_time <= 1.0:
            # Linear interpolation from 100 to 75 points
            points = int(100 - (reaction_time - 0.5) * 50)
        elif reaction_time <= 2.0:
            # Linear interpolation from 75 to 30 points
            points = int(75 - (reaction_time - 1.0) * 45)
        elif reaction_time <= 3.0:
            # Linear interpolation from 30 to 10 points
            points = int(30 - (reaction_time - 2.0) * 20)
        else:
            points = 10
        
        # Ensure minimum 10 points for any tap
        points = max(10, points)
        
        logger.info(f"DEBUG - Calculated points: {points} for reaction time {reaction_time}")
        
        # Ensure scores dict exists for this user
        if user_id not in game_state['scores']:
            game_state['scores'][user_id] = 0
            logger.info(f"DEBUG - Initialized score for user {user_id}")
        
        old_score = game_state['scores'][user_id]
        game_state['scores'][user_id] += points
        new_score = game_state['scores'][user_id]
        logger.info(f"DEBUG - Score update: {old_score} -> {new_score} (+{points})")
        
        # Store this player's tap with precise timestamp
        if 'round_taps' not in game_state:
            game_state['round_taps'] = {}
        game_state['round_taps'][user_id] = {
            'reaction_time': reaction_time,
            'points': points,
            'tap_timestamp': tap_time  # Store exact timestamp for comparison
        }
        logger.info(f"DEBUG - Stored tap data for user {user_id}: {game_state['round_taps'][user_id]}")
        
        logger.info(f"SUCCESS - User {user_id} tapped - time: {reaction_time:.3f}s, points: {points}, total score: {game_state['scores'][user_id]}")
        
        # Send immediate feedback to the player who tapped
        self.send_message(user_id, f"⚡ TAPPED! Your time: {reaction_time:.3f}s (+{points} pts)")
        
        # Allow both players to score - don't end round immediately
        # The timeout will handle the round end to ensure both players can tap
        pass

    def handle_reaction_wrong(self, session_id, user_id):
        """Handle wrong tap (on red/yellow)"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        # Check if this player already got penalized this round to prevent double penalty
        if 'wrong_taps' not in game_state:
            game_state['wrong_taps'] = set()
        
        if user_id in game_state['wrong_taps']:
            return  # Already penalized this round
        
        # Mark this player as having tapped wrong and apply penalty
        game_state['wrong_taps'].add(user_id)
        game_state['scores'][user_id] = game_state['scores'][user_id] - 20
        
        # Send immediate feedback only to the player who tapped wrong
        self.send_message(user_id, f"❌ You tapped the wrong color! -20 points penalty")
        
        # Only trigger round end once - check if this is the first wrong tap processed
        if not game_state.get('fake_out_triggered', False):
            game_state['fake_out_triggered'] = True
            # Continue to next round after penalty
            import threading
            threading.Timer(2.0, lambda: self.handle_fake_out_success(session_id)).start()

    def handle_fake_out_success(self, session_id):
        """Handle fake-out round results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        # Check who tapped wrong this round
        wrong_taps = game_state.get('wrong_taps', set())
        
        # Show personalized results to each player
        for player_id in session['players']:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            player_tapped_wrong = player_id in wrong_taps
            opponent_tapped_wrong = opponent_id in wrong_taps
            
            if player_tapped_wrong and opponent_tapped_wrong:
                # Both tapped wrong
                success_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"❌ <b>Both players tapped wrong!</b> ❌\n\n"
                    f"Both got -20 points penalty!\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            elif player_tapped_wrong:
                # You tapped wrong, opponent didn't
                success_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"❌ <b>You tapped wrong!</b> (-20 pts)\n"
                    f"✅ <b>Opponent avoided it!</b> (0 pts)\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            elif opponent_tapped_wrong:
                # Opponent tapped wrong, you didn't
                success_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"✅ <b>You avoided the fake-out!</b> (0 pts)\n"
                    f"❌ <b>Opponent tapped wrong!</b> (-20 pts)\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            else:
                # Neither tapped wrong
                success_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"✅ <b>Good job! You avoided the fake-out!</b> ✅\n\n"
                    f"Both players correctly didn't tap!\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
            
            self.send_message(player_id, success_text, keyboard)
        
        # Clear wrong taps and fake out trigger for next round
        game_state['wrong_taps'] = set()
        game_state['fake_out_triggered'] = False
        
        # Move to next round after fake-out results (only for fake-out rounds)
        if game_state['round'] >= 5:
            import threading
            threading.Timer(2.0, lambda: self.end_reaction_game(session_id)).start()
        else:
            game_state['round'] += 1
            game_state['ready_players'] = set()
            game_state['target_showing'] = False
            game_state['current_phase'] = 'waiting_ready'
            import threading
            threading.Timer(2.0, lambda: self.update_reaction_display(session_id)).start()
        
    def handle_fake_out_auto_continue(self, session_id):
        """Auto-continue fake-out round if no one tapped wrong"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        # Only continue if no wrong taps occurred, otherwise the wrong tap handler already processed it
        if not game_state.get('fake_out_triggered', False):
            self.handle_fake_out_success(session_id)

    def check_reaction_timeout(self, session_id):
        """Check if reaction round timed out"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        if game_state.get('round_active', False):
            # End round due to timeout - this ensures both players' taps are recorded
            self.handle_reaction_round_end(session_id)

    def handle_reaction_round_end(self, session_id):
        """End reaction round and show results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        # Prevent duplicate execution
        if game_state.get('round_ending', False):
            return
        game_state['round_ending'] = True
        
        game_state['round_active'] = False
        game_state['ready_players'] = set()
        game_state['target_showing'] = False
        
        # Get round results
        round_taps = game_state.get('round_taps', {})
        
        # Show personalized round results
        for player_id in session['players']:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            if player_id in round_taps and opponent_id in round_taps:
                # Both players tapped
                player_time = round_taps[player_id]['reaction_time']
                player_points = round_taps[player_id]['points']
                opponent_time = round_taps[opponent_id]['reaction_time']
                opponent_points = round_taps[opponent_id]['points']
                
                result_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"⏱️ <b>Your time:</b> {player_time:.3f}s (+{player_points} pts)\n"
                    f"⏱️ <b>Opponent:</b> {opponent_time:.3f}s (+{opponent_points} pts)\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            elif player_id in round_taps:
                # Only you tapped
                player_time = round_taps[player_id]['reaction_time']
                player_points = round_taps[player_id]['points']
                
                result_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"⏱️ <b>Your time:</b> {player_time:.3f}s (+{player_points} pts)\n"
                    f"😴 <b>Opponent:</b> Too slow! (0 pts)\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            elif opponent_id in round_taps:
                # Only opponent tapped
                opponent_time = round_taps[opponent_id]['reaction_time']
                opponent_points = round_taps[opponent_id]['points']
                
                result_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"😴 <b>You:</b> Too slow! (0 pts)\n"
                    f"⏱️ <b>Opponent:</b> {opponent_time:.3f}s (+{opponent_points} pts)\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            else:
                # Neither player tapped
                result_text = (
                    f"⚡ <b>Round {game_state['round']} Results</b> ⚡\n\n"
                    f"😴 <b>Both players too slow!</b>\n"
                    f"No points awarded this round.\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
            
            self.send_message(player_id, result_text, keyboard)
        
        # Clear round state
        game_state['round_taps'] = {}
        game_state['round_ending'] = False
        
        # Check if game should end (NO DUPLICATE ROUND PROGRESSION HERE)
        if game_state['round'] >= 5:
            # Small delay then end game
            import threading
            threading.Timer(2.0, lambda: self.end_reaction_game(session_id)).start()
        else:
            # Move to next round - reset ready players and increment round
            game_state['round'] += 1
            game_state['ready_players'] = set()
            game_state['current_phase'] = 'waiting_ready'
            import threading
            threading.Timer(2.0, lambda: self.update_reaction_display(session_id)).start()

    def end_reaction_game(self, session_id):
        """End Reaction Game and show final results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        player1_score = game_state['scores'][player1_id]
        player2_score = game_state['scores'][player2_id]
        
        if player1_score > player2_score:
            winner_id = player1_id
            loser_id = player2_id
        elif player2_score > player1_score:
            winner_id = player2_id
            loser_id = player1_id
        else:
            winner_id = None  # Tie
        
        # Update stats
        if winner_id:
            loser_id = player2_id if winner_id == player1_id else player1_id
            self.update_user_game_result(winner_id, 'reaction', True)
            self.update_user_game_result(loser_id, 'reaction', False)
        else:
            # Tie - no wins awarded
            self.update_user_game_result(player1_id, 'reaction', False)
            self.update_user_game_result(player2_id, 'reaction', False)
        
        # Send personalized results
        for player_id in session['players']:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            if winner_id == player_id:
                final_text = (
                    f"⚡ <b>Reaction Game - FINAL RESULTS</b> ⚡\n\n"
                    f"🎉 <b>YOU WON!</b> 🎉\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Lightning reflexes! You're a reaction master!"
                )
            elif winner_id and winner_id != player_id:
                final_text = (
                    f"⚡ <b>Reaction Game - FINAL RESULTS</b> ⚡\n\n"
                    f"😔 <b>YOU LOST!</b> 😔\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Good effort! Practice makes perfect reflexes!"
                )
            else:
                final_text = (
                    f"⚡ <b>Reaction Game - FINAL RESULTS</b> ⚡\n\n"
                    f"🤝 <b>IT'S A TIE!</b> 🤝\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Perfectly matched reflexes!"
                )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Play Other Games', 'callback_data': 'show_games'}],
                    [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
                ]
            }
            
            self.send_message(player_id, final_text, keyboard)
        
        # Clean up session safely to prevent KeyError
        if session_id in multiplayer_sessions:
            del multiplayer_sessions[session_id]
        
        if winner_id:
            self.check_prize_eligibility(winner_id)

    def start_memory_game(self, session_id):
        """Initialize Memory Match game"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        player1_id, player2_id = session['players']
        
        session['game_state'] = {
            'board': create_memory_board(),
            'current_player': player1_id,
            'scores': {player1_id: 0, player2_id: 0},
            'selected_tiles': [],
            'matched_pairs': 0,
            'total_pairs': 6,
            'turn_locked': False
        }

    def update_memory_display(self, session_id):
        """Update Memory Match display for both players"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        current_player = game_state['current_player']
        
        # Generate board display
        board_text = ""
        for i, row in enumerate(game_state['board']):
            for j, tile in enumerate(row):
                position = i * 4 + j
                if tile['matched']:
                    board_text += tile['symbol']
                elif tile['revealed'] and len(game_state['selected_tiles']) > 0:
                    # Show temporarily revealed tiles only to current player
                    board_text += tile['symbol']
                else:
                    board_text += "⬛"
                board_text += " "
            board_text += "\n"
        
        for player_id in [player1_id, player2_id]:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            is_current_player = (player_id == current_player)
            
            memory_text = (
                f"🧩 <b>Memory Match Game</b> 🧩\n\n"
                f"📋 <b>How to Play:</b>\n"
                f"• Find matching pairs by selecting 2 tiles\n"
                f"• Each turn: pick your first tile, then your second tile\n"
                f"• Match = you get a point and another turn\n"
                f"• No match = other player's turn\n"
                f"• Most pairs wins!\n\n"
                f"{board_text}\n"
                f"Score: You {player_score} - {opponent_score} Opponent\n"
                f"Pairs found: {game_state['matched_pairs']}/6\n\n"
            )
            
            if is_current_player and not game_state.get('turn_locked', False):
                if len(game_state['selected_tiles']) == 0:
                    memory_text += "🎯 <b>Your turn! Select your first tile:</b>"
                elif len(game_state['selected_tiles']) == 1:
                    memory_text += "🎯 <b>Now select your second tile:</b>"
                
                # Create tile buttons for current player
                keyboard_buttons = []
                for i, row in enumerate(game_state['board']):
                    button_row = []
                    for j, tile in enumerate(row):
                        position = i * 4 + j
                        if not tile['matched'] and not tile['revealed']:
                            button_row.append({
                                'text': f'📍 {position + 1}',
                                'callback_data': f'memory_select_{session_id}_{position}'
                            })
                        else:
                            button_row.append({
                                'text': tile['symbol'] if tile['matched'] else '⬛',
                                'callback_data': 'noop'
                            })
                    keyboard_buttons.append(button_row)
                
                keyboard_buttons.append([{'text': '🎮 Quit Game', 'callback_data': 'show_games'}])
                keyboard = {'inline_keyboard': keyboard_buttons}
            else:
                memory_text += f"⏳ <b>Waiting for opponent's move...</b>"
                keyboard = {
                    'inline_keyboard': [
                        [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                    ]
                }
            
            self.send_message(player_id, memory_text, keyboard)

    def handle_memory_select(self, session_id, user_id, position):
        """Handle Memory Match tile selection"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        if user_id != game_state['current_player']:
            return
        
        if game_state.get('turn_locked', False):
            return
        
        position = int(position)
        row, col = position // 4, position % 4
        tile = game_state['board'][row][col]
        
        if tile['matched'] or tile['revealed']:
            return
        
        # Reveal tile
        tile['revealed'] = True
        game_state['selected_tiles'].append(position)
        
        # Check if this is the second tile selection
        if len(game_state['selected_tiles']) == 2:
            game_state['turn_locked'] = True
            
            # Check for match
            pos1, pos2 = game_state['selected_tiles']
            row1, col1 = pos1 // 4, pos1 % 4
            row2, col2 = pos2 // 4, pos2 % 4
            tile1 = game_state['board'][row1][col1]
            tile2 = game_state['board'][row2][col2]
            
            if tile1['symbol'] == tile2['symbol']:
                # Match found!
                tile1['matched'] = True
                tile2['matched'] = True
                game_state['scores'][user_id] += 1
                game_state['matched_pairs'] += 1
                
                # Show match result and continue with same player
                import threading
                threading.Timer(1.5, lambda: self.handle_memory_match_result(session_id, True)).start()
            else:
                # No match - hide tiles and switch player
                import threading
                threading.Timer(1.5, lambda: self.handle_memory_match_result(session_id, False)).start()
        
        # Update display immediately
        self.update_memory_display(session_id)

    def handle_memory_match_result(self, session_id, is_match):
        """Handle Memory Match result and continue game"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        if not is_match:
            # Hide revealed tiles
            for pos in game_state['selected_tiles']:
                row, col = pos // 4, pos % 4
                game_state['board'][row][col]['revealed'] = False
            
            # Switch to other player
            game_state['current_player'] = player2_id if game_state['current_player'] == player1_id else player1_id
        
        # Reset for next turn
        game_state['selected_tiles'] = []
        game_state['turn_locked'] = False
        
        # Check if game is complete
        if game_state['matched_pairs'] >= 6:
            self.end_memory_game(session_id)
        else:
            self.update_memory_display(session_id)

    def end_memory_game(self, session_id):
        """End Memory Match game and show results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        player1_score = game_state['scores'][player1_id]
        player2_score = game_state['scores'][player2_id]
        
        if player1_score > player2_score:
            winner_id = player1_id
        elif player2_score > player1_score:
            winner_id = player2_id
        else:
            winner_id = None  # Tie
        
        # Update stats
        if winner_id:
            loser_id = player2_id if winner_id == player1_id else player1_id
            self.update_user_game_result(winner_id, 'memory', True)
            self.update_user_game_result(loser_id, 'memory', False)
        else:
            self.update_user_game_result(player1_id, 'memory', False)
            self.update_user_game_result(player2_id, 'memory', False)
        
        # Send personalized results
        for player_id in session['players']:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            if winner_id == player_id:
                final_text = (
                    f"🧩 <b>Memory Match - FINAL RESULTS</b> 🧩\n\n"
                    f"🎉 <b>YOU WON!</b> 🎉\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Excellent memory skills! You found {player_score} pairs!"
                )
            elif winner_id and winner_id != player_id:
                final_text = (
                    f"🧩 <b>Memory Match - FINAL RESULTS</b> 🧩\n\n"
                    f"😔 <b>YOU LOST!</b> 😔\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Good effort! You found {player_score} pairs. Practice makes perfect!"
                )
            else:
                final_text = (
                    f"🧩 <b>Memory Match - FINAL RESULTS</b> 🧩\n\n"
                    f"🤝 <b>IT'S A TIE!</b> 🤝\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Perfectly matched memory skills!"
                )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Play Other Games', 'callback_data': 'show_games'}],
                    [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
                ]
            }
            
            self.send_message(player_id, final_text, keyboard)
        
        del multiplayer_sessions[session_id]
        if winner_id:
            self.check_prize_eligibility(winner_id)

    def start_qa_game(self, session_id):
        """Initialize Q&A Duel game"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        player1_id, player2_id = session['players']
        
        session['game_state'] = {
            'round': 1,
            'max_rounds': 6,
            'current_asker': player1_id,
            'current_answerer': player2_id,
            'phase': 'question',  # question, answer, guess
            'scores': {player1_id: 0, player2_id: 0},
            'current_question': '',
            'current_answer': '',
            'waiting_for_input': True
        }

    def update_qa_display(self, session_id):
        """Update Q&A Duel display for both players"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        current_asker = game_state['current_asker']
        current_answerer = game_state['current_answerer']
        current_phase = game_state['phase']
        current_round = game_state['round']
        
        for player_id in [player1_id, player2_id]:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            qa_text = (
                f"🧠 <b>Q&A Duel - Round {current_round}/6</b> 🧠\n\n"
                f"📋 <b>How to Play:</b>\n"
                f"• Step 1: Asker types a question in chat\n"
                f"• Step 2: Asker provides the correct answer\n"
                f"• Step 3: Answerer guesses the answer\n"
                f"• Correct guess = 1 point for answerer\n"
                f"• 6 rounds total = each player asks 3, answers 3!\n\n"
                f"Score: You {player_score} - {opponent_score} Opponent\n\n"
            )
            
            if current_phase == 'question':
                if player_id == current_asker:
                    qa_text += "🎯 <b>Your turn to ask!</b>\n\nType your question in the chat below:"
                else:
                    qa_text += "⏳ <b>Waiting for opponent's question...</b>"
            
            elif current_phase == 'answer':
                if player_id == current_asker:
                    qa_text += f"❓ <b>Your question:</b> {game_state['current_question']}\n\n🎯 <b>Now type the correct answer in chat:</b>"
                else:
                    qa_text += f"❓ <b>Question:</b> {game_state['current_question']}\n\n⏳ <b>Waiting for opponent to provide the answer...</b>"
            
            elif current_phase == 'guess':
                if player_id == current_answerer:
                    qa_text += f"❓ <b>Question:</b> {game_state['current_question']}\n\n🎯 <b>Type your guess in chat:</b>"
                else:
                    qa_text += f"❓ <b>Your question:</b> {game_state['current_question']}\n\n⏳ <b>Waiting for opponent's guess...</b>"
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                ]
            }
            
            self.send_message(player_id, qa_text, keyboard)

    def handle_qa_text_input(self, chat_id, user_id, text):
        """Handle Q&A Duel text input"""
        # Find the session for this user
        session_id = None
        for sid, session in multiplayer_sessions.items():
            if user_id in session['players'] and session['game_type'] == 'qa':
                session_id = sid
                break
        
        if not session_id:
            return False
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        
        if not game_state.get('waiting_for_input', False):
            return False
        
        current_phase = game_state['phase']
        current_asker = game_state['current_asker']
        current_answerer = game_state['current_answerer']
        
        if current_phase == 'question' and user_id == current_asker:
            # Store the question
            game_state['current_question'] = text
            game_state['phase'] = 'answer'
            self.update_qa_display(session_id)
            return True
        
        elif current_phase == 'answer' and user_id == current_asker:
            # Store the correct answer
            game_state['current_answer'] = text
            game_state['phase'] = 'guess'
            self.update_qa_display(session_id)
            return True
        
        elif current_phase == 'guess' and user_id == current_answerer:
            # Check the guess
            correct = check_answer_similarity(game_state['current_answer'], text)
            
            if correct:
                game_state['scores'][current_answerer] += 1
                result_text = "🎉 <b>CORRECT!</b> 🎉\n\n+1 point!"
            else:
                result_text = f"❌ <b>WRONG!</b>\n\nCorrect answer was: {game_state['current_answer']}"
            
            # Show result to both players
            player1_id, player2_id = session['players']
            for player_id in [player1_id, player2_id]:
                opponent_id = player2_id if player_id == player1_id else player1_id
                player_score = game_state['scores'][player_id]
                opponent_score = game_state['scores'][opponent_id]
                
                round_result = (
                    f"🧠 <b>Round {game_state['round']} Results</b> 🧠\n\n"
                    f"❓ <b>Question:</b> {game_state['current_question']}\n"
                    f"✅ <b>Answer:</b> {game_state['current_answer']}\n"
                    f"💭 <b>Guess:</b> {text}\n\n"
                    f"{result_text}\n\n"
                    f"Score: You {player_score} - {opponent_score} Opponent"
                )
                
                keyboard = {
                    'inline_keyboard': [
                        [{'text': '🎮 Quit Game', 'callback_data': 'show_games'}]
                    ]
                }
                
                self.send_message(player_id, round_result, keyboard)
            
            # Check if game should end
            if game_state['round'] >= 6:
                import threading
                threading.Timer(2.0, lambda: self.end_qa_game(session_id)).start()
            else:
                # Next round - switch roles
                game_state['round'] += 1
                game_state['current_asker'] = current_answerer
                game_state['current_answerer'] = current_asker
                game_state['phase'] = 'question'
                game_state['current_question'] = ''
                game_state['current_answer'] = ''
                
                import threading
                threading.Timer(2.0, lambda: self.update_qa_display(session_id)).start()
            
            return True
        
        return False

    def end_qa_game(self, session_id):
        """End Q&A Duel game and show results"""
        if session_id not in multiplayer_sessions:
            return
        
        session = multiplayer_sessions[session_id]
        game_state = session['game_state']
        player1_id, player2_id = session['players']
        
        player1_score = game_state['scores'][player1_id]
        player2_score = game_state['scores'][player2_id]
        
        if player1_score > player2_score:
            winner_id = player1_id
        elif player2_score > player1_score:
            winner_id = player2_id
        else:
            winner_id = None  # Tie
        
        # Update stats
        if winner_id:
            loser_id = player2_id if winner_id == player1_id else player1_id
            self.update_user_game_result(winner_id, 'qa', True)
            self.update_user_game_result(loser_id, 'qa', False)
        else:
            self.update_user_game_result(player1_id, 'qa', False)
            self.update_user_game_result(player2_id, 'qa', False)
        
        # Send personalized results
        for player_id in session['players']:
            opponent_id = player2_id if player_id == player1_id else player1_id
            player_score = game_state['scores'][player_id]
            opponent_score = game_state['scores'][opponent_id]
            
            if winner_id == player_id:
                final_text = (
                    f"🧠 <b>Q&A Duel - FINAL RESULTS</b> 🧠\n\n"
                    f"🎉 <b>YOU WON!</b> 🎉\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Brilliant mind! You answered {player_score} questions correctly!"
                )
            elif winner_id and winner_id != player_id:
                final_text = (
                    f"🧠 <b>Q&A Duel - FINAL RESULTS</b> 🧠\n\n"
                    f"😔 <b>YOU LOST!</b> 😔\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Good thinking! You got {player_score} correct. Keep learning!"
                )
            else:
                final_text = (
                    f"🧠 <b>Q&A Duel - FINAL RESULTS</b> 🧠\n\n"
                    f"🤝 <b>IT'S A TIE!</b> 🤝\n\n"
                    f"Final Score: You {player_score} - {opponent_score} Opponent\n\n"
                    f"Evenly matched intellects!"
                )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎮 Play Other Games', 'callback_data': 'show_games'}],
                    [{'text': '🏆 View Scoreboard', 'callback_data': 'show_scoreboard'}]
                ]
            }
            
            self.send_message(player_id, final_text, keyboard)
        
        del multiplayer_sessions[session_id]
        if winner_id:
            self.check_prize_eligibility(winner_id)

    def handle_game_cancellation(self, chat_id, message_id, user_id, session_id):
        """Handle game cancellation by host"""
        if session_id not in multiplayer_sessions:
            self.edit_message(chat_id, message_id, "❌ Game session no longer exists.", {
                'inline_keyboard': [[{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]]
            })
            return
        
        session = multiplayer_sessions[session_id]
        
        # Only host can cancel the game
        if user_id != session['host_id']:
            self.edit_message(chat_id, message_id, "❌ Only the game host can cancel this game.", {
                'inline_keyboard': [[{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]]
            })
            return
        
        # Remove the session
        game_name = GAMES.get(session['game_type'], {}).get('name', 'Game')
        del multiplayer_sessions[session_id]
        
        cancellation_text = (
            f"❌ <b>Game Cancelled</b> ❌\n\n"
            f"Your {game_name} game has been cancelled.\n\n"
            f"You can create a new game anytime!"
        )
        
        keyboard = {
            'inline_keyboard': [
                [{'text': '🎮 Create New Game', 'callback_data': 'show_games'}],
                [{'text': '🔍 Find Active Games', 'callback_data': 'find_games'}]
            ]
        }
        
        self.edit_message(chat_id, message_id, cancellation_text, keyboard)

    def check_prize_eligibility(self, user_id):
        """Check if user is eligible for prize"""
        if user_id not in game_scores:
            return
        
        total_wins = game_scores[user_id].get('total_wins', 0)
        
        if total_wins >= 3 and not game_scores[user_id].get('prize_claimed', False):
            prize_text = (
                "🎉 <b>CONGRATULATIONS!</b> 🎉\n\n"
                "You've won 3 games and unlocked a special prize!\n\n"
                "Click below to claim your reward!"
            )
            
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎁 Claim Prize!', 'callback_data': 'reveal_prize'}],
                    [{'text': '🎮 Continue Playing', 'callback_data': 'show_games'}]
                ]
            }
            
            self.send_message(user_id, prize_text, keyboard)

    def handle_view_prize(self, chat_id, message_id, user_id):
        """View already claimed prize - shows fake first, then option for real"""
        self.register_user({'id': user_id, 'first_name': 'Player'})
        
        if not game_scores[user_id].get('prize_claimed', False):
            # Haven't claimed yet
            no_prize_text = "❌ You haven't claimed any prize yet! Get 3 wins first."
            keyboard = {
                'inline_keyboard': [
                    [{'text': '🎁 Test Prize (3 wins)', 'callback_data': 'test_prize'}],
                    [{'text': '🎮 Back to Games', 'callback_data': 'show_games'}]
                ]
            }
            self.edit_message(chat_id, message_id, no_prize_text, keyboard)
            return
        
        # Show fake message first with option to view real
        fake_prize_text = (
            "🎁 <b>Your Prize Message</b> 🎁\n\n"
            "🤡🤡🤡 DUMBOOOOO YOU REALLY THINK U WONNNN??? 🤡🤡🤡"
        )
        
        keyboard_buttons = [[{'text': '🎁 View Real Prize', 'callback_data': 'real_prize'}]]
        keyboard_buttons.append([{'text': '🎮 Back to Games', 'callback_data': 'show_games'}])
        
        keyboard = {'inline_keyboard': keyboard_buttons}
        self.edit_message(chat_id, message_id, fake_prize_text, keyboard)

    def handle_callback_query(self, callback_query):
        query_id = callback_query['id']
        user_data = callback_query['from']
        chat_id = callback_query['message']['chat']['id']
        message_id = callback_query['message']['message_id']
        data = callback_query['data']
        user_id = user_data['id']
        
        self.register_user(user_data)
        self.answer_callback_query(query_id)
        
        try:
            if data == 'show_games':
                self.show_game_menu(chat_id, message_id, user_id)
            elif data == 'show_scoreboard':
                self.show_scoreboard(chat_id, message_id, user_id)
            elif data.startswith('invite_'):
                game_type = data.split('_', 1)[1]
                self.create_multiplayer_invitation(chat_id, message_id, user_id, user_data, game_type)
            elif data == 'find_games':
                self.show_active_games(chat_id, message_id)
            elif data.startswith('join_'):
                session_id = data.split('_', 1)[1]
                self.handle_invite_acceptance(chat_id, message_id, user_id, user_data, session_id)
            elif data.startswith('cancel_'):
                session_id = data.split('_', 1)[1]
                self.handle_game_cancellation(chat_id, message_id, user_id, session_id)

            elif data == 'reveal_prize':
                self.handle_prize_reveal(chat_id, message_id, user_id)
            elif data == 'real_prize':
                self.handle_real_prize_reveal(chat_id, message_id, user_id)
            elif data == 'view_prize':
                self.handle_view_prize(chat_id, message_id, user_id)
            elif data.startswith('ttt_'):
                parts = data.split('_')
                if len(parts) >= 4:
                    position = f"{parts[1]}_{parts[2]}"
                    session_id = "_".join(parts[3:])
                    
                    self.answer_callback_query(callback_query['id'], "✅ Move confirmed!")
                    self.handle_tictactoe_move(session_id, user_id, position)
            elif data.startswith('rps_') and not data.startswith('rps_continue_'):
                parts = data.split('_')
                if len(parts) >= 3:
                    choice = parts[1]
                    session_id = "_".join(parts[2:])
                    
                    choice_emojis = {'rock': '🪨', 'paper': '📄', 'scissors': '✂️', 'gun': '🔫', 'judo': '🥋'}
                    emoji = choice_emojis.get(choice, '✅')
                    self.answer_callback_query(callback_query['id'], f"{emoji} {choice.title()} selected!")
                    self.handle_rps_choice(session_id, user_id, choice)
            elif data.startswith('reaction_ready_'):
                session_id = data.split('_', 2)[2]
                self.answer_callback_query(callback_query['id'], "🚀 Ready!")
                self.handle_reaction_ready(session_id, user_id)
            elif data.startswith('reaction_tap_'):
                session_id = data.split('_', 2)[2]
                logger.info(f"Processing reaction tap for user {user_id} in session {session_id}")
                self.answer_callback_query(callback_query['id'], "⚡ TAPPED!")
                self.handle_reaction_tap(session_id, user_id)
            elif data.startswith('reaction_wrong_'):
                session_id = data.split('_', 2)[2]
                self.answer_callback_query(callback_query['id'], "❌ Wrong color!")
                self.handle_reaction_wrong(session_id, user_id)
            elif data.startswith('memory_select_'):
                parts = data.split('_')
                if len(parts) >= 4:
                    session_id = "_".join(parts[2:-1])
                    position = parts[-1]
                    self.answer_callback_query(callback_query['id'], f"📍 Tile {int(position)+1} selected!")
                    self.handle_memory_select(session_id, user_id, position)

            elif data == 'noop':
                pass
            else:
                logger.warning(f"Unknown callback data: {data}")
                
        except Exception as e:
            logger.error(f"Error handling callback query {data}: {e}")

    def process_update(self, update):
        if 'message' in update:
            message = update['message']
            chat_id = message['chat']['id']
            user_data = message['from']
            
            if 'text' in message:
                text = message['text']
                if text.startswith('/start'):
                    self.handle_start(chat_id, user_data)
                elif text.startswith('/play'):
                    self.handle_play_command(chat_id, user_data)
                else:
                    # Check if this is Q&A Duel input
                    if self.handle_qa_text_input(chat_id, user_data['id'], text):
                        return  # Text was handled by Q&A game
                    
                    response_text = (
                        "🤖 I am not sure what you mean.\n\n"
                        "Use /start to begin or click the buttons in the menu!"
                    )
                    self.send_message(chat_id, response_text)
        
        elif 'callback_query' in update:
            self.handle_callback_query(update['callback_query'])

    def get_updates(self, offset=None):
        try:
            params = {'timeout': 10}
            if offset:
                params['offset'] = offset
            response = requests.get(f"{self.api_url}/getUpdates", params=params, timeout=15)
            return response.json()
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return {'ok': False}

    def run(self):
        logger.info("Starting simple local bot...")
        offset = None
        
        while True:
            try:
                result = self.get_updates(offset)
                
                if not result.get('ok'):
                    logger.error(f"Error getting updates: {result}")
                    time.sleep(5)
                    continue
                
                for update in result.get('result', []):
                    try:
                        self.process_update(update)
                        offset = update['update_id'] + 1
                    except Exception as e:
                        logger.error(f"Error processing update: {e}")
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)

# Health check server for Railway deployment
async def health_check(request):
    """Health check endpoint for Railway deployment."""
    return web.Response(text="Railway Bot is running!", status=200)

async def start_health_server():
    """Start health server on port 8080"""
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health server started on port 8080")

def run_bot():
    """Run the bot in a separate thread"""
    bot_token = os.environ.get('BOT_TOKEN')
    
    if not bot_token:
        logger.error("BOT_TOKEN environment variable not set!")
        exit(1)
    
    bot = SimpleLocalBot(bot_token)
    logger.info("Starting Railway production bot...")
    bot.run()

async def main():
    """Main function for Railway deployment"""
    # Start health server
    await start_health_server()
    
    # Start bot in separate thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Keep the server running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())