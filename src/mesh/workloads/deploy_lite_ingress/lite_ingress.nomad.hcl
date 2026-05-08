variable "acme_email" {
  type = string
  description = "Email for Let's Encrypt certificate notifications"
}

variable "caddy_image" {
  type    = string
  default = "caddy:2"
  description = "Caddy Docker image"
}

variable "memory" {
  type    = number
  default = 25
  description = "Memory allocation in MB"
}

variable "cpu" {
  type    = number
  default = 100
  description = "CPU allocation in MHz"
}

variable "datacenter" {
  type    = string
  default = "dc1"
  description = "Nomad datacenter name"
}

variable "log_level" {
  type    = string
  default = "INFO"
  description = "Caddy log level"
}

job "caddy" {
  namespace = "mesh-infra"
  type = "system"
  datacenters = [var.datacenter]

  constraint {
    attribute = "${attr.kernel.name}"
    value     = "linux"
  }

  constraint {
    attribute = "${meta.role}"
    value     = "server"
  }

  group "caddy" {
    network {
      mode = "host"

      port "http" {
        static = 80
        to     = 80
      }

      port "https" {
        static = 443
        to     = 443
      }

      port "admin" {
        static = 2019
        to     = 2019
      }
    }

    volume "caddy-data" {
      type       = "host"
      read_only  = false
      source     = "caddy-data"
    }

    task "caddy" {
      driver = "docker"

      config {
        image = var.caddy_image

        mount {
          type   = "volume"
          target = "/data"
          source = "caddy-data"
        }

        ports = ["http", "https", "admin"]
      }

      template {
        data = <<EOF
{
  admin :2019
  log {
    level "${var.log_level}"
  }
}

:80 {
  redir https://{host}{uri} permanent
}
EOF
        destination = "etc/caddy/Caddyfile"
        change_mode   = "restart"
        change_signal = "SIGHUP"
      }

      resources {
        cpu    = var.cpu
        memory = var.memory
      }
    }
  }
}
