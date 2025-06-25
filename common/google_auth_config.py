from flask_dance.contrib.google import make_google_blueprint, google

app.config["GOOGLE_OAUTH_CLIENT_ID"] = "YOUR_CLIENT_ID"
app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = "YOUR_CLIENT_SECRET"
blueprint = make_google_blueprint(
    scope=["profile", "email"],
    redirect_url="/google_login"
)
app.register_blueprint(blueprint, url_prefix="/login")