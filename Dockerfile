# ---- Build stage ----
FROM golang:1.25.7-alpine3.23 AS builder

WORKDIR /app

RUN apk add --no-cache git ca-certificates

COPY go.mod go.sum ./
RUN go mod download

COPY . .

ARG TARGETOS
ARG TARGETARCH

RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o server ./cmd/server

# ---- Run stage ----
FROM alpine:3.20

WORKDIR /app

RUN apk add --no-cache ca-certificates wget && update-ca-certificates

COPY --from=builder /app/server /app/server

EXPOSE 8080

CMD ["/app/server"]
