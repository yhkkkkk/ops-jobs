package main

import (
	"os"
	"os/signal"
	"syscall"

	"github.com/spf13/cobra"

	"ops-job-agent/internal/config"
	"ops-job-agent/internal/core"
	"ops-job-agent/internal/logger"
)

var rootCmd = &cobra.Command{
	Use:   "agent",
	Short: "ops-job agent service",
}

var startCmd = &cobra.Command{
	Use:   "start",
	Short: "start agent service",
	RunE: func(cmd *cobra.Command, args []string) error {
		cfg, err := config.Load()
		if err != nil {
			return err
		}

		// 初始化日志
		logger.InitLogger(
			cfg.Logging.LogDir,
			cfg.Logging.LogMaxSize,
			cfg.Logging.LogMaxFiles,
			cfg.Logging.LogMaxAge,
			cfg.Logging.LogLevel,
			cfg.Logging.LogFormat,
			cfg.Logging.LogReportCaller,
		)
		log := logger.GetLogger()

		logFields := map[string]interface{}{
			"agent_name":       cfg.Identification.AgentName,
			"agent_server_url": cfg.Connection.AgentServerURL,
		}

		log.WithFields(logFields).Info("starting agent")

		ag := core.NewAgent(cfg)
		if err := ag.Start(); err != nil {
			log.WithError(err).Error("start agent failed")
			return err
		}

		// 等待信号
		ch := make(chan os.Signal, 1)
		signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
		<-ch

		log.Info("shutting down agent...")
		ag.Stop()
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
