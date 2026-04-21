from flask import Flask, render_template, request, redirect, send_file, url_for # type: ignore
from flask_login import LoginManager, login_user, logout_user, login_required, current_user # type: ignore
from werkzeug.security import generate_password_hash, check_password_hash # type: ignore
from models import db, User, Income, Expense

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ------------------ МАРШРУТЫ ------------------



from sqlalchemy import func # type: ignore
import pandas as pd # type: ignore
import os

# ------------------ ГЛАВНАЯ ------------------

@app.route('/')
def index():
    return redirect(url_for('income'))

# ------------------ ДОХОДЫ ------------------

@app.route('/income', methods=['GET', 'POST'])
@login_required
def income():
    if request.method == 'POST':
        name = request.form['name']
        hectares = float(request.form['hectares'])
        price = float(request.form['price'])

        income_value = hectares * price

        new_income = Income(
            name=name,
            hectares=hectares,
            price=price,
            income=income_value,
            user_id=current_user.id
        )

        db.session.add(new_income)
        db.session.commit()

        return redirect(url_for('income'))

    incomes = Income.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes.html', incomes=incomes)

#-------------------delete-------------------

@app.route('/income/delete/<int:id>', methods=['POST'])
@login_required
def delete_income(id):
    income = Income.query.get_or_404(id)

    # защита: нельзя удалить чужие данные
    if income.user_id != current_user.id:
        return "Доступ запрещён", 403

    db.session.delete(income)
    db.session.commit()
    return redirect('/income')

#---------------------------------------------
@app.route('/expense/delete/<int:id>', methods=['POST'])
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)

    # защита: нельзя удалить чужие расходы
    if expense.user_id != current_user.id:
        return "Доступ запрещён", 403

    db.session.delete(expense)
    db.session.commit()
    return redirect('/expense')




# ------------------ РАСХОДЫ ------------------

@app.route('/expense', methods=['GET', 'POST'])
@login_required
def expense():
    if request.method == 'POST':
        new_expense = Expense(
            category=request.form['category'],
            amount=float(request.form['amount']),
            description=request.form['description'],
            user_id=current_user.id
        )

        db.session.add(new_expense)
        db.session.commit()

        return redirect(url_for('expense'))

    expenses = Expense.query.filter_by(user_id=current_user.id).all()
    return render_template('expenses.html', expenses=expenses)

# ------------------ ИТОГ ------------------

@app.route('/summary')
@login_required
def summary():
    income = db.session.query(func.sum(Income.income))\
        .filter_by(user_id=current_user.id).scalar() or 0

    expense = db.session.query(func.sum(Expense.amount))\
        .filter_by(user_id=current_user.id).scalar() or 0

    profit = income - expense

    return render_template(
        'summary.html',
        income=income,
        expense=expense,
        profit=profit
    )

# ------------------ EXCEL ------------------

@app.route('/export')
@login_required
def export_excel():
    incomes = Income.query.filter_by(user_id=current_user.id).all()
    expenses = Expense.query.filter_by(user_id=current_user.id).all()

    incomes_data = [{
        "Имя": i.name,
        "Гектары": i.hectares,
        "Цена": i.price,
        "Доход": i.income,
        "Дата": i.date
    } for i in incomes]

    expenses_data = [{
        "Категория": e.category,
        "Сумма": e.amount,
        "Описание": e.description,
        "Дата": e.date
    } for e in expenses]

    df_income = pd.DataFrame(incomes_data)
    df_expense = pd.DataFrame(expenses_data)

    file_name = f"report_user_{current_user.id}.xlsx"

    with pd.ExcelWriter(file_name, engine="openpyxl") as writer:
        df_income.to_excel(writer, sheet_name="Доходы", index=False)
        df_expense.to_excel(writer, sheet_name="Расходы", index=False)

    return send_file(file_name, as_attachment=True)

#-----------------------Loginmeneger------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Проверка: есть ли пользователь
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "Пользователь уже существует"

        # Хешируем пароль
        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')

#------------------------admin--------------
@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != "admin":
        return "Доступ запрещён", 403

    search = request.args.get('search')

    if search:
        users = User.query.filter(User.username.contains(search)).all()
    else:
        users = User.query.all()

    return render_template("admin.html", users=users)
#------------------карточка-------------------
@app.route('/user/<int:user_id>')
@login_required
def user_card(user_id):
    if current_user.role != "admin":
        return "Доступ запрещён", 403

    user = User.query.get_or_404(user_id)

    incomes = Income.query.filter_by(user_id=user.id).all()
    expenses = Expense.query.filter_by(user_id=user.id).all()

    total_income = sum(i.income for i in incomes)
    total_expense = sum(e.amount for e in expenses)
    profit = total_income - total_expense

    return render_template(
        "user_card.html",
        user=user,
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        profit=profit
    )
 #-----------------------------login--------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return redirect(url_for('income'))

        return "Неверный логин или пароль"

    return render_template('login.html')

#--------------------exitakaunt----------

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
