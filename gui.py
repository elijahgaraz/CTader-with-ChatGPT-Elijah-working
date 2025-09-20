import time
import threading
import tkinter as tk
import queue
from tkinter import ttk, messagebox, simpledialog
from typing import List, Dict, Any # Added for type hinting
import pandas as pd # Added for OHLC data handling
from trading import Trader, AiAdvice, Position # adjust import path if needed
from strategies import (
    SafeStrategy, ModerateStrategy, AggressiveStrategy,
    MomentumStrategy, MeanReversionStrategy
)
from indicators import (
    calculate_ema, calculate_atr, calculate_rsi, calculate_adx
)
from ttkthemes import ThemedTk

class MainApplication(ThemedTk):
    def __init__(self, settings):
        super().__init__(theme="arc")
        self.title("Forex Scalper")

        # make window resizable
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.settings = settings
        self._ui_queue = queue.Queue()
        self.trader = Trader(
            self.settings,
            on_account_update=self._handle_account_update,
            on_positions_update=self._handle_positions_update
        )
        self.after(100, self._process_ui_queue)


        container = ttk.Frame(self)
        container.grid(row=0, column=0, sticky="nsew")
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.pages = {}

        # Create SettingsPage separately as it's not in the notebook
        settings_page = SettingsPage(container, self)
        settings_page.grid(row=0, column=0, sticky="nsew")
        self.pages[SettingsPage] = settings_page

        # Create the Notebook for other pages
        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Create and add pages to the notebook
        self.trading_page = TradingPage(self.notebook, self)
        self.performance_page = PerformancePage(self.notebook, self)

        self.notebook.add(self.trading_page, text="Trading")
        self.notebook.add(self.performance_page, text="Performance")

        self.pages[TradingPage] = self.trading_page
        self.pages[PerformancePage] = self.performance_page

        self.show_page(SettingsPage)

    def show_page(self, page_cls):
        if page_cls in [TradingPage, PerformancePage]:
            # If we want to show a page that is in the notebook,
            # we must first raise the notebook itself.
            self.notebook.tkraise()
            # Then select the correct tab.
            if page_cls == TradingPage:
                self.notebook.select(self.trading_page)
            elif page_cls == PerformancePage:
                self.notebook.select(self.performance_page)
        else:
            # For pages not in the notebook (like SettingsPage)
            page = self.pages[page_cls]
            page.tkraise()

    def _handle_account_update(self, summary: Dict[str, Any]):
        """Callback for the Trader to push account updates."""
        self._ui_queue.put(("account_update", summary))

    def _handle_positions_update(self, positions: Dict[int, Position]):
        """Callback for the Trader to push position updates."""
        self._ui_queue.put(("positions_update", positions))

    def _process_ui_queue(self):
        """Process items from the UI queue."""
        try:
            while True:
                msg_type, data = self._ui_queue.get_nowait()

                trading_page = self.pages.get(TradingPage)
                performance_page = self.pages.get(PerformancePage)

                if msg_type == "account_update":
                    for page in self.pages.values():
                        if hasattr(page, "update_account_info"):
                            page.update_account_info(
                                account_id=data.get("account_id", "–"),
                                balance=data.get("balance"),
                                equity=data.get("equity"),
                                margin=data.get("margin")
                            )
                elif msg_type == "positions_update":
                    if performance_page and hasattr(performance_page, "update_positions"):
                        performance_page.update_positions(data)
                elif msg_type == "show_ai_advice":
                    if trading_page:
                        trading_page._show_ai_advice(data)
                elif msg_type == "show_ai_error":
                    if trading_page:
                        trading_page._show_ai_error(data)
                elif msg_type == "re-enable_ai_button":
                    if trading_page:
                        trading_page.ai_button.config(state="normal")
                elif msg_type == "_log":
                    if trading_page:
                        trading_page._log(data)
                elif msg_type == "_execute_trade":
                    if trading_page:
                        trading_page._execute_trade(*data)

        except queue.Empty:
            pass
        finally:
            self.after(100, self._process_ui_queue)


class SettingsPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=10)
        self.controller = controller

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0) # Right column for hours
        self.rowconfigure(1, weight=1)

        # --- Left Column ---
        left_column = ttk.Frame(self)
        left_column.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 5))
        left_column.rowconfigure(1, weight=1)
        left_column.columnconfigure(0, weight=1)

        # --- Credentials ---
        creds = ttk.Labelframe(left_column, text="Credentials", padding=10)
        creds.grid(row=0, column=0, sticky="ew")
        creds.columnconfigure(1, weight=1)

        self.client_id_var = tk.StringVar(value=self.controller.settings.openapi.client_id or "")
        ttk.Label(creds, text="Client ID:").grid(row=0, column=0, sticky="w", padx=(0,5))
        ttk.Entry(creds, textvariable=self.client_id_var).grid(row=0, column=1, sticky="ew")

        self.client_secret_var = tk.StringVar(value=self.controller.settings.openapi.client_secret or "")
        ttk.Label(creds, text="Client Secret:").grid(row=1, column=0, sticky="w", padx=(0,5))
        ttk.Entry(creds, textvariable=self.client_secret_var, show="*").grid(row=1, column=1, sticky="ew")

        self.advisor_auth_token_var = tk.StringVar(value=self.controller.settings.ai.advisor_auth_token or "")
        ttk.Label(creds, text="AI Advisor Token:").grid(row=2, column=0, sticky="w", padx=(0,5))
        ttk.Entry(creds, textvariable=self.advisor_auth_token_var, show="*").grid(row=2, column=1, sticky="ew")

        self.account_id_entry_var = tk.StringVar(value=self.controller.settings.openapi.default_ctid_trader_account_id or "")
        ttk.Label(creds, text="Account ID:").grid(row=3, column=0, sticky="w", padx=(0,5))
        ttk.Entry(creds, textvariable=self.account_id_entry_var).grid(row=3, column=1, sticky="ew")

        # --- Account Summary ---
        acct = ttk.Labelframe(left_column, text="Account Summary", padding=10)
        acct.grid(row=1, column=0, sticky="nsew", pady=(10,0))
        acct.columnconfigure(1, weight=1)

        self.account_id_var = tk.StringVar(value="–")
        ttk.Label(acct, text="Account ID:").grid(row=0, column=0, sticky="w", padx=(0,5))
        ttk.Label(acct, textvariable=self.account_id_var).grid(row=0, column=1, sticky="w")

        self.balance_var = tk.StringVar(value="–")
        ttk.Label(acct, text="Balance:").grid(row=1, column=0, sticky="w", padx=(0,5))
        ttk.Label(acct, textvariable=self.balance_var).grid(row=1, column=1, sticky="w")

        self.equity_var = tk.StringVar(value="–")
        ttk.Label(acct, text="Equity:").grid(row=2, column=0, sticky="w", padx=(0,5))
        ttk.Label(acct, textvariable=self.equity_var).grid(row=2, column=1, sticky="w")

        self.margin_var = tk.StringVar(value="–")
        ttk.Label(acct, text="Margin:").grid(row=3, column=0, sticky="w", padx=(0,5))
        ttk.Label(acct, textvariable=self.margin_var).grid(row=3, column=1, sticky="w")

        # --- Right Column for other settings ---
        right_column = ttk.Frame(self)
        right_column.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(5, 0))
        right_column.rowconfigure(0, weight=0)
        right_column.columnconfigure(0, weight=1)

        # --- Trading Hours ---
        hours = ttk.Labelframe(right_column, text="Trading Session (UTC)", padding=10)
        hours.grid(row=0, column=0, sticky="ew")
        hours.columnconfigure(1, weight=1)

        self.start_hour_var = tk.StringVar(value=str(self.controller.settings.general.trading_start_hour))
        ttk.Label(hours, text="Start Hour:").grid(row=0, column=0, sticky="w", padx=(0,5))
        ttk.Entry(hours, textvariable=self.start_hour_var, width=5).grid(row=0, column=1, sticky="w")

        self.end_hour_var = tk.StringVar(value=str(self.controller.settings.general.trading_end_hour))
        ttk.Label(hours, text="End Hour:").grid(row=1, column=0, sticky="w", padx=(0,5))
        ttk.Entry(hours, textvariable=self.end_hour_var, width=5).grid(row=1, column=1, sticky="w")

        # --- Bottom Row for Actions and Status ---
        bottom_row = ttk.Frame(self)
        bottom_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10,0))
        bottom_row.columnconfigure(0, weight=1)

        actions = ttk.Frame(bottom_row)
        actions.pack(side="top", fill="x", expand=True)
        ttk.Button(actions, text="Save Settings", command=self.save_settings).pack(side="left", padx=5)
        ttk.Button(actions, text="Connect", command=self.attempt_connection).pack(side="left", padx=5)

        self.status = ttk.Label(bottom_row, text="Disconnected", anchor="center")
        self.status.pack(side="top", fill="x", expand=True, pady=(5,0))

    def update_account_info(self, account_id: str, balance: float | None, equity: float | None, margin: float | None):
        self.account_id_var.set(str(account_id) if account_id is not None else "–")
        self.balance_var.set(f"{balance:.2f}" if balance is not None else "–")
        self.equity_var.set(f"{equity:.2f}" if equity is not None else "–")
        self.margin_var.set(f"{margin:.2f}" if margin is not None else "–")

    def save_settings(self):
        self.controller.settings.openapi.client_id = self.client_id_var.get()
        self.controller.settings.openapi.client_secret = self.client_secret_var.get()
        self.controller.settings.ai.advisor_auth_token = self.advisor_auth_token_var.get()
        try:
            self.controller.settings.general.trading_start_hour = int(self.start_hour_var.get())
            self.controller.settings.general.trading_end_hour = int(self.end_hour_var.get())
            self.controller.settings.openapi.default_ctid_trader_account_id = int(self.account_id_entry_var.get())
        except (ValueError, TypeError):
            self.controller.settings.openapi.default_ctid_trader_account_id = None
            messagebox.showerror("Invalid Input", "Trading hours and Account ID must be valid integers.")

        self._log(f"[Settings] Saving start hour: {self.controller.settings.general.trading_start_hour}")
        self._log(f"[Settings] Saving end hour: {self.controller.settings.general.trading_end_hour}")

        self.controller.settings.save()
        messagebox.showinfo("Settings Saved", "Your settings have been saved successfully.")

    def attempt_connection(self):
        t = self.controller.trader
        t.settings = self.controller.settings
        self.status.config(text="Processing connection...", foreground="orange")

        def _connect_thread_target():
            if t.connect():
                self.after(0, lambda: self.status.config(text="Connection successful. Authenticating account...", foreground="orange"))
                self.after(100, self._check_connection)
            else:
                _, msg = t.get_connection_status()
                final_msg = f"Failed: {msg}" if msg else "Connection failed."
                self.after(0, lambda: messagebox.showerror("Connection Failed", final_msg))
                self.after(0, lambda: self.status.config(text=final_msg, foreground="red"))
        threading.Thread(target=_connect_thread_target, daemon=True).start()
        
    def _check_connection(self):
        t = self.controller.trader
        connected, msg = t.get_connection_status()
        if connected:
            self._on_successful_connection(t)
        else:
            if msg:
                messagebox.showerror("Connection Failed", msg)
                self.status.config(text=f"Failed: {msg}", foreground="red")
            else:
                self.after(200, self._check_connection)

    def _on_successful_connection(self, t):
        summary = t.get_account_summary()
        account_id_from_summary = summary.get("account_id")
        if account_id_from_summary in ["connecting...", "–", None] or summary.get("balance") is None:
            self.status.config(text="Fetching account details...", foreground="orange")
            self.after(300, lambda: self._on_successful_connection(t))
            return
        
        self.update_account_info(
            summary.get("account_id"),
            summary.get("balance"),
            summary.get("equity"),
            summary.get("margin")
        )
        messagebox.showinfo("Connected", f"Successfully connected to account {summary.get('account_id')}")
        self.status.config(text="Connected ✅", foreground="green")

        available_symbols = t.get_available_symbol_names()
        if available_symbols:
            self.controller.pages[TradingPage].populate_symbols_dropdown(available_symbols)
        else:
            self.controller.pages[TradingPage].populate_symbols_dropdown([])
            self._log_to_trading_page("Warning: No symbols received from the trader.")
        self.controller.show_page(TradingPage)

    def _log_to_trading_page(self, message: str):
        if TradingPage in self.controller.pages:
            self.controller.pages[TradingPage]._log(f"[SettingsPage] {message}")


class PerformancePage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=10)
        self.controller = controller
        self.trader = controller.trader
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        columns = ("id", "symbol", "side", "volume", "open_price", "pnl")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        for col in columns:
            self.tree.heading(col, text=col.replace("_", " ").title())
        self.tree.column("pnl", anchor="e")
        self.tree.bind("<Double-1>", self._on_trade_double_click)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        close_all_button = ttk.Button(self, text="Close All Positions", command=self.trader.close_all_positions)
        close_all_button.grid(row=1, column=0, columnspan=2, pady=(10, 0))

    def _on_trade_double_click(self, event):
        selection = self.tree.selection()
        if not selection: return
        item_id = selection[0]
        position_id_to_close = int(self.tree.item(item_id, "values")[0])
        if messagebox.askyesno("Confirm Close", f"Are you sure you want to close position {position_id_to_close}?"):
            self.trader.close_position(position_id_to_close)

    def update_positions(self, open_positions: Dict[int, Position]):
        current_ids_in_tree = set(self.tree.get_children())
        for pos_id, pos_data in open_positions.items():
            item_id = str(pos_id)
            pnl_color = "green" if pos_data.current_pnl >= 0 else "red"
            self.tree.tag_configure(pnl_color, foreground=pnl_color)
            values = (
                pos_id, pos_data.symbol_name, pos_data.trade_side,
                f"{pos_data.volume_lots:.2f}", f"{pos_data.open_price:.5f}", f"{pos_data.current_pnl:.2f}"
            )
            if item_id in current_ids_in_tree:
                self.tree.item(item_id, values=values, tags=(pnl_color,))
                current_ids_in_tree.remove(item_id)
            else:
                self.tree.insert("", "end", iid=item_id, values=values, tags=(pnl_color,))
        for item_id_to_remove in current_ids_in_tree:
            self.tree.delete(item_id_to_remove)


class TradingPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=10)
        self.controller = controller
        self.trader = controller.trader
        self.is_scalping = False
        self.scalping_thread = None

        self.account_id_var_tp = tk.StringVar(value="–")
        self.balance_var_tp = tk.StringVar(value="–")
        self.equity_var_tp = tk.StringVar(value="–")

        for r in range(13): self.rowconfigure(r, weight=0)
        self.rowconfigure(13, weight=1)
        self.columnconfigure(1, weight=1)

        ttk.Button(self, text="← Settings", command=lambda: controller.show_page(SettingsPage)).grid(
            row=0, column=0, columnspan=2, pady=(0,10), sticky="w")

        acc_info_frame = ttk.Labelframe(self, text="Account Information", padding=5)
        acc_info_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0,10))
        acc_info_frame.columnconfigure(1, weight=1)
        ttk.Label(acc_info_frame, text="Account ID:").grid(row=0, column=0, sticky="w", padx=(0,5))
        ttk.Label(acc_info_frame, textvariable=self.account_id_var_tp).grid(row=0, column=1, sticky="w")
        ttk.Label(acc_info_frame, text="Balance:").grid(row=1, column=0, sticky="w", padx=(0,5))
        ttk.Label(acc_info_frame, textvariable=self.balance_var_tp).grid(row=1, column=1, sticky="w")
        ttk.Label(acc_info_frame, text="Equity:").grid(row=2, column=0, sticky="w", padx=(0,5))
        ttk.Label(acc_info_frame, textvariable=self.equity_var_tp).grid(row=2, column=1, sticky="w")

        ttk.Label(self, text="Symbol:").grid(row=2, column=0, sticky="w", padx=(0,5))
        self.symbol_var = tk.StringVar(value="Loading symbols...")
        self.cb_symbol = ttk.Combobox(self, textvariable=self.symbol_var, values=[], state="readonly")
        self.cb_symbol.grid(row=2, column=1, sticky="ew")
        self.cb_symbol.bind("<<ComboboxSelected>>", lambda e: self.trader.handle_symbol_selection(self.symbol_var.get()))

        ttk.Label(self, text="Price:").grid(row=3, column=0, sticky="w", padx=(0,5))
        self.price_var = tk.StringVar(value="–")
        pf = ttk.Frame(self)
        pf.grid(row=3, column=1, sticky="ew")
        ttk.Label(pf, textvariable=self.price_var, font=("TkDefaultFont", 12, "bold")).pack(side="left")

        ttk.Label(self, text="Profit Target (pips):").grid(row=4, column=0, sticky="w", padx=(0,5))
        self.tp_var = tk.DoubleVar(value=10.0)
        ttk.Entry(self, textvariable=self.tp_var).grid(row=4, column=1, sticky="ew")

        ttk.Label(self, text="Order Size (lots):").grid(row=5, column=0, sticky="w", padx=(0,5))
        self.size_var = tk.DoubleVar(value=1.0)
        ttk.Entry(self, textvariable=self.size_var).grid(row=5, column=1, sticky="ew")

        ttk.Label(self, text="Stop Loss (pips):").grid(row=6, column=0, sticky="w", padx=(0,5))
        self.sl_var = tk.DoubleVar(value=5.0)
        ttk.Entry(self, textvariable=self.sl_var).grid(row=6, column=1, sticky="ew")

        ttk.Label(self, text="Batch Profit Target:").grid(row=7, column=0, sticky="w", padx=(0,5))
        self.batch_profit_var = tk.DoubleVar(value=self.controller.settings.general.batch_profit_target)
        ttk.Entry(self, textvariable=self.batch_profit_var).grid(row=7, column=1, sticky="ew")

        ttk.Label(self, text="Strategy:").grid(row=8, column=0, sticky="w", padx=(0,5))
        self.strategy_var = tk.StringVar(value="Safe")
        strategy_names = ["Safe", "Moderate", "Aggressive", "Momentum", "Mean Reversion"]
        cb_strat = ttk.Combobox(self, textvariable=self.strategy_var, values=strategy_names, state="readonly")
        cb_strat.grid(row=8, column=1, sticky="ew")
        cb_strat.bind("<<ComboboxSelected>>", lambda e: self._update_data_readiness_display(execute_now=True))

        ttk.Label(self, text="Data Readiness:").grid(row=9, column=0, sticky="w", padx=(0,5), pady=(10,0))
        self.data_readiness_var = tk.StringVar(value="Initializing...")
        self.data_readiness_label = ttk.Label(self, textvariable=self.data_readiness_var)
        self.data_readiness_label.grid(row=9, column=1, sticky="ew", pady=(10,0))

        self.ai_button = ttk.Button(self, text="ChatGPT Analysis", command=self.run_chatgpt_analysis)
        self.ai_button.grid(row=10, column=0, columnspan=2, pady=(10, 0))

        self.start_button = ttk.Button(self, text="Begin Scalping", command=self.start_scalping, state="normal")
        self.start_button.grid(row=11, column=0, columnspan=2, pady=(10,0))
        self.stop_button  = ttk.Button(self, text="Stop Scalping", command=self.stop_scalping, state="disabled")
        self.stop_button.grid(row=12, column=0, columnspan=2, pady=(5,0))

        stats = ttk.Labelframe(self, text="Session Stats", padding=10)
        stats.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(10,0))
        stats.columnconfigure(1, weight=1)
        self.pnl_var = tk.StringVar(value="0.00")
        self.trades_var = tk.StringVar(value="0")
        self.win_rate_var = tk.StringVar(value="0%")
        ttk.Label(stats, text="P&L:").grid(row=0, column=0, sticky="w", padx=(0,5))
        ttk.Label(stats, textvariable=self.pnl_var).grid(row=0, column=1, sticky="w")
        ttk.Label(stats, text="# Trades:").grid(row=1, column=0, sticky="w", padx=(0,5))
        ttk.Label(stats, textvariable=self.trades_var).grid(row=1, column=1, sticky="w")
        ttk.Label(stats, text="Win Rate:").grid(row=2, column=0, sticky="w", padx=(0,5))
        ttk.Label(stats, textvariable=self.win_rate_var).grid(row=2, column=1, sticky="w")

        self.output = tk.Text(self, height=8, wrap="word", state="disabled")
        self.output.grid(row=14, column=0, columnspan=2, sticky="nsew", pady=(10,0))
        sb = ttk.Scrollbar(self, command=self.output.yview)
        sb.grid(row=14, column=2, sticky="ns")
        self.output.config(yscrollcommand=sb.set)

        self.total_pnl, self.total_trades, self.wins, self.current_batch_trades, self.batch_start_equity = 0.0, 0, 0, 0, 0.0
        self.batch_size = 5
        self.after(1000, self._update_data_readiness_display)

    def _update_data_readiness_display(self, execute_now=False):
        if not self.trader or not self.trader.is_connected:
            self.data_readiness_var.set("Trader disconnected")
            self.data_readiness_label.config(foreground="gray")
            self.start_button.config(state="disabled")
            if not execute_now: self.after(2000, self._update_data_readiness_display)
            return

        strategy_name = self.strategy_var.get()
        # This is a bit inefficient, but safe. Could be optimized by caching.
        strategy_map = {
            "Safe": SafeStrategy, "Moderate": ModerateStrategy, "Aggressive": AggressiveStrategy,
            "Momentum": MomentumStrategy, "Mean Reversion": MeanReversionStrategy
        }
        strategy_class = strategy_map.get(strategy_name)
        if not strategy_class:
            self.data_readiness_var.set("Select a strategy")
            self.start_button.config(state="disabled")
            if not execute_now: self.after(1000, self._update_data_readiness_display)
            return

        strategy_instance = strategy_class(self.controller.settings)
        required_bars_map = strategy_instance.get_required_bars()
        symbol = self.symbol_var.get().replace("/", "")
        available_bars_map = self.trader.get_ohlc_bar_counts(symbol)

        self._log(f"[DataReadiness] Checking for {symbol}. Required: {required_bars_map}. Available: {available_bars_map}")

        all_ready = True
        status_messages = []
        if not required_bars_map:
            status_messages.append("No specific bar data required.")
        else:
            for tf, required_count in required_bars_map.items():
                available_count = available_bars_map.get(tf, 0)
                status_messages.append(f"{tf}: {available_count}/{required_count}")
                if available_count < required_count: all_ready = False

        final_status_text = ", ".join(status_messages)
        if all_ready:
            final_status_text += " (Ready)"
            self.data_readiness_label.config(foreground="green")
            self.start_button.config(state="normal" if not self.is_scalping else "disabled")
        else:
            final_status_text += " (Waiting...)"
            self.data_readiness_label.config(foreground="orange")
            self.start_button.config(state="disabled")

        self.data_readiness_var.set(final_status_text)
        if not execute_now: self.after(2000, self._update_data_readiness_display)

    def populate_symbols_dropdown(self, symbol_names: List[str]):
        if not symbol_names:
            self.cb_symbol.config(values=[])
            self.symbol_var.set("No symbols available")
            return
        self.cb_symbol.config(values=symbol_names)
        configured_default = self.controller.settings.general.default_symbol
        if configured_default in symbol_names:
            self.symbol_var.set(configured_default)
        elif symbol_names:
            self.symbol_var.set(symbol_names[0])
        self.trader.handle_symbol_selection(self.symbol_var.get())

    def update_account_info(self, account_id: str, balance: float | None, equity: float | None, margin: float | None):
        self.account_id_var_tp.set(str(account_id) if account_id is not None else "–")
        self.balance_var_tp.set(f"{balance:.2f}" if balance is not None else "–")
        self.equity_var_tp.set(f"{equity:.2f}" if equity is not None else "–")

    def run_chatgpt_analysis(self):
        self._log("Requesting ChatGPT Analysis...")
        self.ai_button.config(state="disabled")
        threading.Thread(target=self._chatgpt_analysis_thread, daemon=True).start()

    def _chatgpt_analysis_thread(self):
        try:
            symbol = self.symbol_var.get().replace("/", "")
            price = self.trader.get_market_price(symbol)
            ohlc_1m_df = self.trader.ohlc_history.get(symbol, {}).get('1m', pd.DataFrame())
            if price is None or ohlc_1m_df.empty:
                self.controller._ui_queue.put(("show_ai_error", "Could not perform analysis: Market data is missing."))
                return

            features = { "price_bid": price, "ema_fast": calculate_ema(ohlc_1m_df, 9).iloc[-1], "ema_slow": calculate_ema(ohlc_1m_df, 21).iloc[-1], "rsi": calculate_rsi(ohlc_1m_df, 14).iloc[-1], "atr": calculate_atr(ohlc_1m_df, 14).iloc[-1], "spread_pips": 0 }
            bot_proposal = { "side": "n/a", "sl_pips": self.sl_var.get(), "tp_pips": self.tp_var.get() }
            advice = self.trader.get_ai_advice(symbol, "long", features, bot_proposal)

            if advice: self.controller._ui_queue.put(("show_ai_advice", advice))
            else: self.controller._ui_queue.put(("show_ai_error", "Failed to get advice from the AI Overseer."))
        except Exception as e:
            self.controller._ui_queue.put(("show_ai_error", f"An error occurred during analysis: {e}"))
        finally:
            self.controller._ui_queue.put(("re-enable_ai_button", None))

    def _show_ai_advice(self, advice: AiAdvice):
        self._log(f"ChatGPT Analysis Result: {advice.action.upper()} (Conf: {advice.confidence:.2%}) - {advice.reason}")
        messagebox.showinfo("ChatGPT Analysis", f"Direction: {advice.action.upper()}\nConfidence: {advice.confidence:.2%}\n\nReason: {advice.reason}")

    def _show_ai_error(self, message: str):
        self._log(f"ChatGPT Analysis Error: {message}")
        messagebox.showerror("ChatGPT Analysis Failed", message)

    def start_scalping(self):
        strategy_name = self.strategy_var.get()
        strategy_map = { "Safe": SafeStrategy, "Moderate": ModerateStrategy, "Aggressive": AggressiveStrategy, "Momentum": MomentumStrategy, "Mean Reversion": MeanReversionStrategy }
        strategy_class = strategy_map.get(strategy_name)
        if not strategy_class:
            messagebox.showerror("Error", "Could not create the selected strategy.")
            return

        strategy = strategy_class(self.controller.settings)
        self._log(f"Strategy created: {strategy.NAME}")

        symbol, tp, sl, size, batch_target = self.symbol_var.get().replace("/", ""), self.tp_var.get(), self.sl_var.get(), self.size_var.get(), self.batch_profit_var.get()
        summary = self.trader.get_account_summary()
        self.batch_start_equity = summary.get("equity", 0.0) or 0.0
        self.current_batch_trades = 0

        self._toggle_scalping_ui(True)
        self.scalping_thread = threading.Thread(target=self._scalp_loop, args=(symbol, tp, sl, size, strategy, batch_target), daemon=True)
        self.scalping_thread.start()
        messagebox.showinfo("Scalping Started", f"Live scalping thread started for {symbol}")

    def stop_scalping(self):
        if self.is_scalping:
            self._toggle_scalping_ui(False)
            try: self.trader.close_all_positions()
            except Exception as e: self._log(f"Error closing positions: {e}")

    def _toggle_scalping_ui(self, on: bool):
        self.is_scalping = on
        self.start_button.config(state="disabled" if on else "normal")
        self.stop_button.config(state="normal" if on else "disabled")

    def _scalp_loop(self, symbol: str, tp: float, sl: float, size: float, strategy, batch_target: float):
        while self.is_scalping:
            if self.current_batch_trades >= self.batch_size:
                summary = self.trader.get_account_summary()
                equity = summary.get("equity", 0.0) or 0.0
                if equity - self.batch_start_equity >= batch_target:
                    self.controller._ui_queue.put(("_log", "Batch profit target reached. Closing positions."))
                    try: self.trader.close_all_positions()
                    except Exception as e: self.controller._ui_queue.put(("_log", f"Error closing positions: {e}"))
                    self.batch_start_equity = equity
                    self.current_batch_trades = 0
            
            current_tick_price = self.trader.get_market_price(symbol)
            if current_tick_price is None:
                time.sleep(1)
                continue

            ohlc_data = {
                '1m': self.trader.ohlc_history.get(symbol, {}).get('1m', pd.DataFrame()),
                '15s': self.trader.ohlc_history.get(symbol, {}).get('15s', pd.DataFrame())
            }
            action_details = strategy.decide(symbol, {**ohlc_data, 'current_equity': self.trader.equity, 'current_price_tick': current_tick_price}, self.trader)

            if action_details and isinstance(action_details, dict):
                trade_action = action_details.get('action')
                if trade_action in ("buy", "sell"):
                    self.controller._ui_queue.put(("_log", f"Strategy signal: {trade_action.upper()} for {symbol}."))
                    self.controller._ui_queue.put(("_execute_trade", (trade_action, symbol, current_tick_price, size, tp, sl, action_details.get('sl_offset'), action_details.get('tp_offset'), action_details.get('comment', ''))))
            time.sleep(1)
   
    def _execute_trade(self, side: str, symbol: str, price: float, size: float, tp_pips_gui: float, sl_pips_gui: float, sl_offset_strategy: float | None, tp_offset_strategy: float | None, strategy_comment: str):
        if price is None:
            self._log("Trade execution skipped: Market price is unavailable.")
            return

        final_tp_pips = tp_offset_strategy if tp_offset_strategy is not None else tp_pips_gui
        final_sl_pips = sl_offset_strategy if sl_offset_strategy is not None else sl_pips_gui

        self._log(f"Attempting to place market order: {side.upper()} {size} lots of {symbol}")
        success, message = self.trader.place_market_order(symbol_name=symbol, volume_lots=size, side=side, take_profit_pips=final_tp_pips, stop_loss_pips=final_sl_pips)

        if success:
            self._log(f"Order request successful: {message}")
            self.total_trades += 1
            self.trades_var.set(str(self.total_trades))
            self.current_batch_trades += 1
        else:
            self._log(f"Order request failed: {message}")
 
    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self.output.configure(state="normal")
        self.output.insert("end", f"[{ts}] {msg}\n")
        self.output.see("end")
        self.output.configure(state="disabled")

if __name__ == "__main__":
    import settings
    app = MainApplication(settings.Settings.load())
    app.mainloop()
