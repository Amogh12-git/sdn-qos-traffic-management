h4 pkill -f receiver.py
h5 pkill -f receiver.py
h6 pkill -f receiver.py
h4 python3 app/receiver.py --port 5001 --label A --run demo &
h5 python3 app/receiver.py --port 5002 --label B --run demo &
h6 python3 app/receiver.py --port 5003 --label C --run demo &
h1 python3 app/sender.py --dst 10.0.0.4 --port 5001 --rate 100 --size 200 --duration 10 --label A &
h2 python3 app/sender.py --dst 10.0.0.5 --port 5002 --rate 250 --size 1000 --duration 10 --label B &
h3 python3 app/sender.py --dst 10.0.0.6 --port 5003 --rate 1786 --size 1400 --duration 10 --label C &
