package main

import (
	"os"
	"os/signal"
	"syscall"

	"ops-job-agent-server/internal/config"
	"ops-job-agent-server/internal/logger"
	"ops-job-agent-server/internal/server"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "agent-server",
	Short: "Agent-Server service",
}

var startCmd = &cobra.Command{
	Use:   "start",
	Short: "start agent-server service",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := config.Load()
		if err != nil {
			return err
		}

		// 初始化日志
		logger.InitLogger(
			cfg.Logging.Dir,
			cfg.Logging.MaxSize,
			cfg.Logging.MaxFiles,
			cfg.Logging.MaxAge,
			cfg.Logging.Level,
		)
		log := logger.GetLogger()

		log.WithFields(map[string]interface{}{
			"host": cfg.Server.Host,
			"port": cfg.Server.Port,
		}).Info("starting agent-server")

		// 创建服务器
		srv, err := server.New(cfg)
		if err != nil {
			log.WithError(err).Fatal("create server failed")
		}

		if err := srv.Start(); err != nil {
			log.WithError(err).Error("start server failed")
			return err
		}

		// 等待信号
		ch := make(chan os.Signal, 1)
		signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
		<-ch

		log.Info("shutting down agent-server...")
		srv.Stop()
		return nil
	},
}

func init() {
	rootCmd.AddCommand(startCmd)
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}
