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
		logger.InitLogger(cfg.LogDir, cfg.LogMaxSize, cfg.LogMaxFiles, cfg.LogMaxAge)
		log := logger.GetLogger()

		logFields := map[string]interface{}{
			"agent_name": cfg.AgentName,
			"mode":       cfg.Mode,
		}
		if cfg.Mode == "direct" {
			logFields["control_plane_url"] = cfg.ControlPlaneURL
		} else {
			logFields["agent_server_url"] = cfg.AgentServerURL
		}

		log.WithFields(logFields).Info("starting agent")

		ag := core.NewAgent(cfg)
		if err := ag.Start(); err != nil {
			log.WithError(err).Error("start agent failed")
			return err
		}

		// wait for signal
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
