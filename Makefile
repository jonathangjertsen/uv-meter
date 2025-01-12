.PHONY: server run-server

server:
	go build -o ./bin/server github.com/jonathangjertsen/uv-meter/server

run-server: server
	./bin/server