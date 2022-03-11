
from flask import Response, send_file
from flask import Flask
from flask import render_template

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


@app.route("/")
def index():
    # return the rendered template
    return render_template("index.html")


@app.route("/playlist.m3u8")
def playlist():
    return send_file(f"/dev/shm/playlist.m3u8")


@app.route("/segment_<int:segment_id>.ts")
def segment(segment_id):
    app.logger.debug(f"looking for segment {segment_id}")
    return send_file(f"/dev/shm/segment_{segment_id:05d}.ts")


# @app.route("/video_feed")
# def video_feed():
#     # return the response generated along with the specific media
#     # type (mime type)
#     return Response(cam.generator(fps=1, resolution=(1280, 960)),
#                     mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == '__main__':
    # start the flask app
    app.run(host="0.0.0.0", port=5000, debug=True,
            threaded=True, use_reloader=False)
