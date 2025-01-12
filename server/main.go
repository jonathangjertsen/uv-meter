package main

import (
	"context"
	"encoding/binary"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/lmittmann/tint"
)

type SensorConfig struct {
	PointNAveraged  uint32 // Number of points to average for point measurement. Max 4.29 billion
	PointDelayUs    uint32 // Microseconds between averaged point measurements. Max 72 minutes
	PointIntervalMs uint32 // Milliseconds between point measurements. Max 49 days
	PointReserved0  uint32 // Reserved
	BurstNSamples   uint32 // Number of points to collect in a burst. Max 4.29 billion
	BurstDelayUs    uint32 // Microseconds between burst measurements. Max 72 minutes
	BurstIntervalMs uint32 // Milliseconds between burst measurements. Max 49 days
	BurstReserved0  uint32 // Reserved
	Expiration      uint32 // Seconds until this config expires. Max. very long
}

var DefaultConfig = SensorConfig{
	PointNAveraged:  64,
	PointDelayUs:    0,
	PointIntervalMs: 1000 * 1,

	BurstNSamples:   512,
	BurstDelayUs:    100,
	BurstIntervalMs: 10000 * 1,

	Expiration: 10,
}

func main() {
	ctx := context.Background()
	logger := slog.New(tint.NewHandler(os.Stdout, nil))

	logger.InfoContext(ctx, "server started")
	err := runServer(ctx, logger)
	logger.InfoContext(ctx, "server exited", "err", err)
}

func runServer(ctx context.Context, serverLogger *slog.Logger) error {
	router := http.NewServeMux()

	router.HandleFunc("POST /point/{id}", func(w http.ResponseWriter, r *http.Request) {
		logger := serverLogger.With("endpoint", "POST /point/{id}")

		// Get id
		id := r.PathValue("id")
		if id == "" {
			logger.ErrorContext(ctx, "missing 'id' path value")
			return
		}
		logger = logger.With("id", id)

		// Read body
		body := make([]byte, 2)
		if n, err := r.Body.Read(body); n != 2 {
			logger.ErrorContext(ctx, "wrong body size", "err", err, "size", n)
			return
		}

		// Parse body
		measurement := binary.BigEndian.Uint16(body)

		// Emit
		logger.InfoContext(ctx, "point measurement", "measurement", measurement)
	})

	router.HandleFunc("POST /burst/{id}", func(w http.ResponseWriter, r *http.Request) {
		logger := serverLogger.With("endpoint", "POST /burst/{id}")

		// Get id
		id := r.PathValue("id")
		if id == "" {
			logger.ErrorContext(ctx, "missing 'id' path value")
			return
		}
		logger = logger.With("id", id)

		// Read body
		body, err := io.ReadAll(r.Body)
		if err != nil {
			logger.ErrorContext(ctx, "reading body", "err", err)
			return
		} else if len(body)&1 != 0 {
			logger.ErrorContext(ctx, "odd body size", "size", len(body))
			return
		}

		// Decode measurements
		measurements := make([]uint16, len(body)/2)
		if n, err := binary.Decode(body, binary.BigEndian, measurements); err != nil {
			logger.ErrorContext(ctx, "error decoding measurements", "err", err)
			return
		} else if n != len(body) {
			logger.ErrorContext(ctx, "decoded wrong n bytes", "expect", len(body), "have", n)
			return
		}

		// Emit
		logger.InfoContext(ctx, "burst measurement", "measurements", measurements, "body", body)
	})

	router.HandleFunc("GET /config/{id}", func(w http.ResponseWriter, r *http.Request) {
		logger := serverLogger.With("endpoint", "GET /config/{id}")

		// Get ID
		id := r.PathValue("id")
		if id == "" {
			logger.ErrorContext(ctx, "missing 'id' path value")
			return
		}
		logger = logger.With("id", id)

		// Write body
		if err := binary.Write(w, binary.BigEndian, DefaultConfig); err != nil {
			logger.ErrorContext(ctx, "error writing config", "err", err)
			return
		}

		// OK
		logger.InfoContext(ctx, "wrote config", "config", DefaultConfig)
	})

	srv := &http.Server{
		Addr:           ":8090",
		Handler:        router,
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   10 * time.Second,
		MaxHeaderBytes: 1 << 20,
	}
	return srv.ListenAndServe()
}
