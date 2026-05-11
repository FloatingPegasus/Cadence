from flask import Flask, render_template, request, jsonify
from datetime import datetime, date
from models.database import db
from models.habit_log import HabitLog
from models.habit import Habit

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

    if not Habit.query.filter_by(user_id=1).first():
        initial_habits = ['Coding', 'Exercise', 'Internship', 'Reading']
        for name in initial_habits:
            new_habit = Habit(name=name, user_id=1)
            db.session.add(new_habit)
        db.session.commit()
        print("Database seeded with initial habits!")

CURRENT_USER_ID = 1

@app.route('/log_habit', methods=['POST'])
def habitLog():
    data = request.get_json()
    
    h_id = data['habit_id']
    h_day = int(data['day'])
    h_val = data['value']

    existing_log = HabitLog.query.filter_by(
        user_id = CURRENT_USER_ID,
        habit_id = h_id,
        day = h_day
    ).first()

    if (h_val == '1' and not existing_log):
        new_log = HabitLog (user_id = CURRENT_USER_ID, habit_id = h_id, day = h_day)
        db.session.add(new_log)
        db.session.commit()
        print(f"Successfully added")
    elif (h_val == '0' and existing_log):
        db.session.delete(existing_log)
        db.session.commit()
        print(f"Removed existing log")

    return jsonify({"status": "success"}), 200

# @app.route('/debug_logs')
# def debugLog():
#     return jsonify(habit_logs)

@app.route('/')
def index():
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    view_date = datetime.strptime(month_str, '%Y-%m').date()

    db_habits = Habit.query.filter_by(user_id=1).all()
    all_logs = HabitLog.query.filter(
        HabitLog.user_id == 1,
        HabitLog.date >= view_date.replace(day=1)
        ).all()
    
    lookup = {}

    for log in all_logs:
        lookup[(log.habit_id, log.day)] = 1
    
    return render_template('index.html', habits=db_habits, lookup=lookup, current_month=month_str)

if __name__=='__main__':
    app.run()