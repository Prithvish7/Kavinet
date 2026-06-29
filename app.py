import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import bcrypt

app = Flask(__name__)
app.secret_key = 'kavinet_secret_key'

# MySQL Configuration


app.config['MYSQL_HOST'] = os.environ.get('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQL_PASSWORD', 'root123')
app.config['MYSQL_DB'] = os.environ.get('MYSQL_DATABASE', 'kavinet')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQL_PORT', 3306))

mysql = MySQL(app)

# ─────────────────────────────────────────
# HOME FEED
# ─────────────────────────────────────────


@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    cur = mysql.connection.cursor()

    # get total count
    cur.execute("SELECT COUNT(*) FROM poems")
    total = cur.fetchone()[0]

    # get only 10 poems for this page
    cur.execute("""
        SELECT poems.*, users.username 
        FROM poems 
        JOIN users ON poems.user_id = users.id 
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    poems = cur.fetchall()
    cur.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template('index.html',
                           poems=poems,
                           page=page,
                           total_pages=total_pages)
# ─────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        hashed = bcrypt.hashpw(password, bcrypt.gensalt())

        cur = mysql.connection.cursor()
        # check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s", [email])
        if cur.fetchone():
            flash('Email already registered. Please login.', 'warning')
            return redirect(url_for('login'))

        cur.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed.decode('utf-8'))
        )
        mysql.connection.commit()
        cur.close()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.checkpw(password, user[3].encode('utf-8')):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Welcome back, ' + user[1] + '!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))


# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT * FROM poems WHERE user_id = %s ORDER BY created_at DESC",
        [session['user_id']]
    )
    poems = cur.fetchall()

    cur.execute(
        "SELECT COUNT(*) FROM followers WHERE following_id = %s",
        [session['user_id']]
    )
    followers = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM followers WHERE follower_id = %s",
        [session['user_id']]
    )
    following = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM books WHERE user_id = %s",
        [session['user_id']]
    )
    book_count = cur.fetchone()[0]

    cur.close()
    return render_template('dashboard.html',
                           poems=poems,
                           followers=followers,
                           following=following,
                           book_count=book_count)


# ─────────────────────────────────────────
# POSTS (POEMS / SONGS / PROSE / STORIES)
# ─────────────────────────────────────────
@app.route('/post_poem', methods=['GET', 'POST'])
def post_poem():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        genre = request.form['genre']

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO poems (user_id, title, content, genre) VALUES (%s, %s, %s, %s)",
            (session['user_id'], title, content, genre)
        )
        mysql.connection.commit()
        cur.close()
        flash('Published successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('post_poem.html')


@app.route('/delete_poem/<int:poem_id>')
def delete_poem(poem_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    # only allow owner to delete
    cur.execute(
        "DELETE FROM poems WHERE id = %s AND user_id = %s",
        (poem_id, session['user_id'])
    )
    mysql.connection.commit()
    cur.close()
    flash('Post deleted.', 'info')
    return redirect(url_for('dashboard'))


# ─────────────────────────────────────────
# LIKES
# ─────────────────────────────────────────
@app.route('/like/<int:poem_id>')
def like(poem_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id FROM likes WHERE user_id = %s AND poem_id = %s",
        (session['user_id'], poem_id)
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO likes (user_id, poem_id) VALUES (%s, %s)",
            (session['user_id'], poem_id)
        )
        cur.execute(
            "UPDATE poems SET likes = likes + 1 WHERE id = %s",
            [poem_id]
        )
        mysql.connection.commit()
    cur.close()
    return redirect(request.referrer or url_for('index'))


# ─────────────────────────────────────────
# MARKETPLACE
# ─────────────────────────────────────────
@app.route('/marketplace')
def marketplace():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT books.*, users.username 
        FROM books 
        JOIN users ON books.user_id = users.id 
        ORDER BY created_at DESC
    """)
    books = cur.fetchall()
    cur.close()
    return render_template('marketplace.html', books=books)


@app.route('/add_book', methods=['GET', 'POST'])
def add_book():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        genre = request.form['genre']

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO books (user_id, title, description, price, genre) VALUES (%s, %s, %s, %s, %s)",
            (session['user_id'], title, description, price, genre)
        )
        mysql.connection.commit()
        cur.close()
        flash('Book listed successfully!', 'success')
        return redirect(url_for('marketplace'))
    return render_template('add_book.html')


# ─────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────
@app.route('/profile/<username>')
def profile(username):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE username = %s", [username])
    user = cur.fetchone()

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('index'))

    cur.execute(
        "SELECT * FROM poems WHERE user_id = %s ORDER BY created_at DESC",
        [user[0]]
    )
    poems = cur.fetchall()

    cur.execute(
        "SELECT * FROM books WHERE user_id = %s ORDER BY created_at DESC",
        [user[0]]
    )
    books = cur.fetchall()

    cur.execute(
        "SELECT COUNT(*) FROM followers WHERE following_id = %s", [user[0]]
    )
    followers = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM followers WHERE follower_id = %s", [user[0]]
    )
    following = cur.fetchone()[0]

    cur.close()
    return render_template('profile.html',
                           user=user,
                           poems=poems,
                           books=books,
                           followers=followers,
                           following=following)


# ─────────────────────────────────────────
# FOLLOW
# ─────────────────────────────────────────
@app.route('/follow/<int:user_id>')
def follow(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session['user_id'] == user_id:
        flash("You can't follow yourself.", 'warning')
        return redirect(request.referrer or url_for('index'))

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT id FROM followers WHERE follower_id = %s AND following_id = %s",
        (session['user_id'], user_id)
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO followers (follower_id, following_id) VALUES (%s, %s)",
            (session['user_id'], user_id)
        )
        mysql.connection.commit()
    cur.close()
    return redirect(request.referrer or url_for('index'))


# ─────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────
@app.route('/search')
def search():
    query = request.args.get('q', '').strip()
    poems = []
    books = []
    users = []

    if query:
        like_query = f"%{query}%"
        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT poems.*, users.username FROM poems 
            JOIN users ON poems.user_id = users.id
            WHERE poems.title LIKE %s OR poems.content LIKE %s OR poems.genre LIKE %s
            ORDER BY created_at DESC
        """, (like_query, like_query, like_query))
        poems = cur.fetchall()

        cur.execute("""
            SELECT books.*, users.username FROM books
            JOIN users ON books.user_id = users.id
            WHERE books.title LIKE %s OR books.description LIKE %s
            ORDER BY created_at DESC
        """, (like_query, like_query))
        books = cur.fetchall()

        cur.execute(
            "SELECT * FROM users WHERE username LIKE %s", [like_query]
        )
        users = cur.fetchall()
        cur.close()

    return render_template('search_results.html',
                           query=query,
                           poems=poems,
                           books=books,
                           users=users)

# ─────────────────────────────────────────
# BUY BOOK
# ─────────────────────────────────────────


@app.route('/buy/<int:book_id>')
def buy_book(book_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    # prevent buying your own book
    cur.execute("SELECT user_id, title FROM books WHERE id = %s", [book_id])
    book = cur.fetchone()

    if not book:
        flash('Book not found.', 'danger')
        return redirect(url_for('marketplace'))

    if book[0] == session['user_id']:
        flash("You can't buy your own book.", 'warning')
        return redirect(url_for('marketplace'))

    # check if already ordered
    cur.execute(
        "SELECT id FROM orders WHERE buyer_id = %s AND book_id = %s",
        (session['user_id'], book_id)
    )
    if cur.fetchone():
        flash('You already own this book.', 'info')
        return redirect(url_for('marketplace'))

    # place order
    cur.execute(
        "INSERT INTO orders (buyer_id, book_id, status) VALUES (%s, %s, 'completed')",
        (session['user_id'], book_id)
    )
    mysql.connection.commit()
    cur.close()

    flash(f'🎉 You bought "{book[1]}" successfully!', 'success')
    return redirect(url_for('marketplace'))

# ─────────────────────────────────────────
# EDIT PROFILE
# ─────────────────────────────────────────


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        bio = request.form.get('bio', '')
        facebook = request.form.get('facebook', '')
        instagram = request.form.get('instagram', '')
        whatsapp = request.form.get('whatsapp', '')
        twitter = request.form.get('twitter', '')

        cur.execute("""
            UPDATE users 
            SET bio=%s, facebook=%s, instagram=%s, whatsapp=%s, twitter=%s
            WHERE id=%s
        """, (bio, facebook, instagram, whatsapp, twitter, session['user_id']))
        mysql.connection.commit()
        cur.close()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile', username=session['username']))

    cur.execute("SELECT * FROM users WHERE id = %s", [session['user_id']])
    user = cur.fetchone()
    cur.close()
    return render_template('edit_profile.html', user=user)


# ─────────────────────────────────────────
# CONTACT PAGE
# ─────────────────────────────────────────
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # just flash for now — can hook to email later
        flash('Thanks for reaching out! The KaviNet team will get back to you soon.', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')


if __name__ == '__main__':
    app.run(debug=True)
