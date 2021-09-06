FROM python:3.9

# Copy function code
COPY app.py /
COPY library /library
# Install the function's dependencies using file requirements.txt
# from your project folder.

COPY requirements.txt  /
RUN  pip3 install -r /requirements.txt

EXPOSE 8024
# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "python",  "/app.py" ] 