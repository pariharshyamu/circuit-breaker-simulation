import pygame
import sys
import copy
import time

# --- Pygame Initialization ---
pygame.init()

# --- Constants ---
# Screen
SCREEN_WIDTH = 1300 # Increased width for more columns
SCREEN_HEIGHT = 850
FPS = 30
# Colors (RGB)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_LIGHT = (210, 210, 210)
GRAY_DARK = (100, 100, 100)
RED = (211, 47, 47) # Material Red
GREEN = (56, 142, 60) # Material Green
BLUE = (25, 118, 210) # Material Blue
YELLOW = (251, 192, 45) # Material Yellow
ORANGE = (255, 143, 0) # Material Orange
CYAN_LIGHT = (129, 212, 250) # Breaker Open
PINK_LIGHT = (244, 143, 177) # K94 Energized
GRAY_MEDIUM = (158, 158, 158) # De-energized Coil / KDC Off
GREEN_LIGHT = (165, 214, 167) # K86 Reset / KDC On
COLOR_DC_POS = (255, 215, 0) # Gold/yellow for DC +
COLOR_DC_NEG = (120, 120, 120) # Gray for DC -

# Schematic Layout
POWER_CIRCUIT_WIDTH = 200
CONTROL_CIRCUIT_X_START = POWER_CIRCUIT_WIDTH + 70
CONTROL_BUS_X_START = CONTROL_CIRCUIT_X_START - 15
BUS_Y_TOP = 60
BUS_Y_BOTTOM = SCREEN_HEIGHT - 60
BUS_X_START_CTRL = CONTROL_CIRCUIT_X_START - 15
BUS_X_END_CTRL = SCREEN_WIDTH - 30
CCOL_WIDTH = 180
CCOL1_X = CONTROL_CIRCUIT_X_START + CCOL_WIDTH * 0.5 # Closing
CCOL2_X = CONTROL_CIRCUIT_X_START + CCOL_WIDTH * 1.5 # Trip Inputs/TC1
CCOL3_X = CONTROL_CIRCUIT_X_START + CCOL_WIDTH * 2.5 # K86
CCOL4_X = CONTROL_CIRCUIT_X_START + CCOL_WIDTH * 3.5 # K1 / Aux Relays
CCOL5_X = CONTROL_CIRCUIT_X_START + CCOL_WIDTH * 4.5 # KDC
COMP_HEIGHT = 16
V_SPACE = 35

# Font
try:
    DEFAULT_FONT = pygame.font.SysFont('Segoe UI', 16)
    LABEL_FONT = pygame.font.SysFont('Segoe UI', 12)
    SMALL_FONT = pygame.font.SysFont('Segoe UI', 10)
    TITLE_FONT = pygame.font.SysFont('Segoe UI', 18, bold=True)
except: # Fallback if Segoe UI not found
    DEFAULT_FONT = pygame.font.Font(None, 20)
    LABEL_FONT = pygame.font.Font(None, 16)
    SMALL_FONT = pygame.font.Font(None, 14)
    TITLE_FONT = pygame.font.Font(None, 24)

# --- Switchgear Panel Logic Class ---
class SwitchgearPanel:
    """ Holds the state and logic, independent of Pygame. """
    def __init__(self):
        self.initial_state = {
            'breaker_state': 'OPEN', 'k86_state': 'RESET', 'kdc_state': 'ENERGIZED',
            'spring_charged': True, 'dc_ok': True, 'dc_fail_alarm': False,
            'tc_healthy': True, 'breaker_in_service': True, 'bus_not_earthed': True,
            'bus_voltage_healthy': True, 'buscoupler_interlock_closed': True,
            'ktc_state': 'ENERGIZED', 'k1_relay_energized': False, 'k1_state': 'DE-ENERGIZED',
            'k94_state': 'DE-ENERGIZED',
            'remote_close_command_active': False, 'trip_signal_s2': False, 'trip_signal_k2': False,
            'trip_signal_kt': False, 'trip_signal_sync': False, 'trip_signal_uv': False,
            'trip_signal_bf': False, 'trip_signal_protection': False, # K86 Coil path
            'trip_signal_k86_no': False, # K86 NO contact state for trip path
            'operation_in_progress': False
        }
        self.state = copy.deepcopy(self.initial_state)
        self._update_dependent_states() # Initial update

    def _update_dependent_states(self):
        self.state['kdc_state'] = 'ENERGIZED' if self.state['dc_ok'] else 'DE-ENERGIZED'
        self.state['dc_fail_alarm'] = not self.state['dc_ok']
        self.state['ktc_state'] = 'ENERGIZED' if self.state['tc_healthy'] and self.state['dc_ok'] else 'DE-ENERGIZED'
        self.state['k94_state'] = 'ENERGIZED' if self.state['breaker_state'] == 'CLOSED' and self.state['dc_ok'] else 'DE-ENERGIZED'
        self.state['k1_state'] = 'ENERGIZED' if self.state['k1_relay_energized'] and self.state['dc_ok'] else 'DE-ENERGIZED'
        self.state['trip_signal_k86_no'] = (self.state['k86_state'] == 'LATCHED')

    def reset_simulation(self):
        if self.state['operation_in_progress']: return False
        print("--- Resetting Simulation ---")
        self.state = copy.deepcopy(self.initial_state)
        self._update_dependent_states()
        return True

    def check_closing_interlocks(self):
        # KTC NO contact: requires KTC ENERGIZED (TC Healthy)
        return (self.state['dc_ok'] and
                self.state['ktc_state'] == 'ENERGIZED' and
                self.state['k1_state'] == 'ENERGIZED' and # K1 must be ON (toggle state)
                self.state['breaker_in_service'] and
                self.state['bus_not_earthed'] and
                self.state['bus_voltage_healthy'] and
                self.state['buscoupler_interlock_closed'] and
                self.state['k86_state'] == 'RESET' and
                self.state['k94_state'] == 'DE-ENERGIZED' and # Check anti-pump
                self.state['breaker_state'] == 'OPEN' and # Check 52b
                self.state['spring_charged'])

    def _recharge_spring(self):
        if not self.state['spring_charged'] and self.state['dc_ok']:
            print("  Spring Recharging...")
            self.state['spring_charged'] = True
            print("  Spring Recharged.")

    def attempt_close(self):
        """Called when K1 pulse is active, attempts the close action."""
        if self.state['operation_in_progress'] or not self.state['remote_close_command_active']:
             return False # Don't close if busy or no active command

        if self.check_closing_interlocks():
            self.state['operation_in_progress'] = True
            print("  Closing Breaker...")
            self.state['breaker_state'] = 'CLOSING'
            self.state['spring_charged'] = False
            # Simulate closing time visually (handled by main loop delay)
            return True # Signal success
        else:
            print("  Close Blocked! Interlocks not met.")
            return False

    def finish_close(self):
        """Completes the closing sequence."""
        self.state['breaker_state'] = 'CLOSED'
        self._update_dependent_states()
        print(f"  Breaker state changed to: {self.state['breaker_state']}")
        self._recharge_spring()
        self.state['operation_in_progress'] = False

    def initiate_direct_trip(self, source_flag_name, reason):
        if self.state['operation_in_progress'] or self.state['breaker_state'] != 'CLOSED' or not self.state['dc_ok']:
            return False
        self.state['operation_in_progress'] = True
        print(f"\n--- Trip Command Received ({reason}) ---")
        self.state[source_flag_name] = True # Activate the source flag
        self.state['breaker_state'] = 'TRIPPING'
        # Simulate trip time visually
        return True

    def finish_direct_trip(self, source_flag_name):
         self.state[source_flag_name] = False # Deactivate flag
         self.state['breaker_state'] = 'OPEN'
         self._update_dependent_states()
         print(f"  Breaker state changed to: {self.state['breaker_state']}")
         self.state['operation_in_progress'] = False

    def initiate_protection_trip(self):
        if self.state['operation_in_progress'] or self.state['breaker_state'] != 'CLOSED' or not self.state['dc_ok']:
            return False
        self.state['operation_in_progress'] = True
        print("\n--- Protection Trip Command Received (-> K86) ---")
        self.state['trip_signal_protection'] = True # K86 Coil path active
        self.state['k86_state'] = 'LATCHED'
        self.state['breaker_state'] = 'TRIPPING'
        self._update_dependent_states() # Update K86_NO flag
        # Simulate trip time visually
        return True

    def finish_protection_trip(self):
        self.state['trip_signal_protection'] = False
        self.state['breaker_state'] = 'OPEN'
        self._update_dependent_states()
        print(f"  Breaker state changed to: {self.state['breaker_state']} - K86 LATCHED")
        self.state['operation_in_progress'] = False

    def reset_k86(self):
        if self.state['operation_in_progress'] or self.state['k86_state'] == 'RESET' or not self.state['dc_ok']:
            return False
        print("\n--- Resetting K86 ---")
        self.state['k86_state'] = 'RESET'
        self._update_dependent_states() # Update K86_NO flag
        print("  K86 Relay Reset.")
        return True

    # --- Toggle Methods ---
    def toggle_dc(self):
        if self.state['operation_in_progress']: return
        self.state['dc_ok'] = not self.state['dc_ok']
        print(f"\n--- DC Power Toggled {'ON' if self.state['dc_ok'] else 'OFF'} ---")
        if not self.state['dc_ok']:
            self.state['k1_relay_energized'] = False
            self.state['remote_close_command_active'] = False
            for key in self.state:
                if key.startswith('trip_signal_'): self.state[key] = False
        self._update_dependent_states()
        if self.state['dc_ok']: self._recharge_spring()

    def toggle_tc_healthy(self):
        if self.state['operation_in_progress'] or not self.state['dc_ok']: return
        self.state['tc_healthy'] = not self.state['tc_healthy']
        print(f"\n--- Trip Coil Supervision Toggled: {'OK' if self.state['tc_healthy'] else 'FAIL'} ---")
        self._update_dependent_states() # Updates KTC

    def toggle_k1(self):
        """Toggles the K1 relay ON/OFF state"""
        if self.state['operation_in_progress'] or not self.state['dc_ok']: return False
        self.state['k1_relay_energized'] = not self.state['k1_relay_energized']
        self._update_dependent_states() # Update k1_state
        print(f"\n--- K1 Relay Toggled {'ON' if self.state['k1_relay_energized'] else 'OFF'} ---")
        if self.state['k1_relay_energized']:
             # If toggled ON, set the pulse flag and immediately check/attempt close
             self.state['remote_close_command_active'] = True
             print("  (Close command pulse initiated)")
             return self.attempt_close() # Return true if close starts
        else:
            # If toggled OFF, ensure pulse flag is also off
            self.state['remote_close_command_active'] = False
            return False # No close action on toggle off

    def end_k1_pulse(self):
         """Called after a delay when K1 is toggled ON"""
         self.state['remote_close_command_active'] = False
         print("  (Close command pulse ended)")


    # --- Other Toggles (simplified: just flip state) ---
    def toggle_service_pos(self):
        if self.state['operation_in_progress']: return
        self.state['breaker_in_service'] = not self.state['breaker_in_service']
        print(f"\n--- Service Position Toggled: {'SERVICE' if self.state['breaker_in_service'] else 'TEST/DRAWN'} ---")
        self._update_dependent_states()

    def toggle_bus_earth(self):
        if self.state['operation_in_progress']: return
        self.state['bus_not_earthed'] = not self.state['bus_not_earthed']
        print(f"\n--- Bus Earth Status Toggled: {'Not Earthed (OK)' if self.state['bus_not_earthed'] else 'EARTHED (Block)'} ---")
        self._update_dependent_states()

    def toggle_bus_v_healthy(self):
        if self.state['operation_in_progress']: return
        self.state['bus_voltage_healthy'] = not self.state['bus_voltage_healthy']
        print(f"\n--- Bus Voltage Toggled: {'Healthy (OK)' if self.state['bus_voltage_healthy'] else 'Low (Block)'} ---")
        self._update_dependent_states()

    def toggle_buscoupler_interlock(self):
        if self.state['operation_in_progress']: return
        self.state['buscoupler_interlock_closed'] = not self.state['buscoupler_interlock_closed']
        print(f"\n--- Bus Coupler Interlock (NC) Toggled: {'CLOSED (OK)' if self.state['buscoupler_interlock_closed'] else 'OPEN (Block)'} ---")
        self._update_dependent_states()

    def toggle_pt_fail(self, phase):
         if self.state['operation_in_progress']: return
         pt_key = f'pt_ok_{phase}'
         if pt_key in self.state:
              self.state[pt_key] = not self.state[pt_key]
              print(f"\n--- PT {phase} Phase Toggled: {'OK' if self.state[pt_key] else 'FAIL'} ---")
         self._update_dependent_states()


# --- Pygame Drawing Functions ---
def drawLine(screen, x1, y1, x2, y2, energized, color=GRAY_LIGHT, width=1.5):
    line_color = ORANGE if energized else color
    line_width = width + 1 if energized else width
    pygame.draw.line(screen, line_color, (x1, y1), (x2, y2), int(line_width))

# --- Main Drawing Function ---
def draw_schematic(screen, panel):
    """Draws the entire schematic based on the panel state."""
    screen.fill(WHITE) # Clear screen

    try:
        # --- Debug Rectangle ---
        pygame.draw.rect(screen, GREEN, (5, 5, 10, 10))

        # --- Power Circuit ---
        pc_x_center = POWER_CIRCUIT_WIDTH / 2
        pc_bus_y_top = BUS_Y_TOP + 60
        pc_bus_y_bottom = BUS_Y_BOTTOM - 60
        pc_cb_y = (pc_bus_y_top + pc_bus_y_bottom) / 2 - 42
        title_surf = TITLE_FONT.render("Power Circuit", True, GRAY_DARK)
        screen.blit(title_surf, (pc_x_center - title_surf.get_width() // 2, BUS_Y_TOP))
        # Buses
        pygame.draw.rect(screen, RED, (pc_x_center - 45, pc_bus_y_top - 4, 90, 8))
        pygame.draw.rect(screen, RED, (pc_x_center - 45, pc_bus_y_bottom - 4, 90, 8))
        # PT
        pt_w, pt_h = 50, 35
        pt_y = pc_bus_y_top + 30
        pt_rect = pygame.Rect(pc_x_center - pt_w / 2, pt_y, pt_w, pt_h)
        pygame.draw.rect(screen, GRAY_LIGHT, pt_rect)
        pygame.draw.rect(screen, GRAY_DARK, pt_rect, 1)
        pt_text = SMALL_FONT.render("Line PT", True, BLACK)
        screen.blit(pt_text, (pt_rect.centerx - pt_text.get_width() // 2, pt_rect.centery - pt_text.get_height() // 2))
        pygame.draw.line(screen, RED, (pc_x_center, pc_bus_y_top), (pc_x_center, pt_y), 4)
        # Breaker Symbol
        draw_breaker_symbol_pygame(screen, pc_x_center, pc_cb_y, panel.state, True)
        # Connections
        line_color = RED if panel.state['breaker_state'] == 'CLOSED' else GRAY_DARK
        pygame.draw.line(screen, line_color, (pc_x_center, pt_y + pt_h + 10), (pc_x_center, pc_cb_y), 4)
        pygame.draw.line(screen, line_color, (pc_x_center, pc_cb_y + 85), (pc_x_center, pc_bus_y_bottom), 4)


        # --- Control Circuit Area ---
        draw_bus_pygame(screen, BUS_Y_TOP, "DC +", COLOR_DC_POS, CONTROL_BUS_X_START, BUS_X_END_CTRL)
        draw_bus_pygame(screen, BUS_Y_BOTTOM, "DC -", COLOR_DC_NEG, CONTROL_BUS_X_START, BUS_X_END_CTRL)

        currentY, y, pathEnergized = 0,0,False # Reset for control

        # --- Closing Circuit (Col 1) ---
        draw_title(screen, "Closing Circuit", CCOL1_X, BUS_Y_TOP - 25)
        pathEnergized = panel.state['dc_ok']
        y = BUS_Y_TOP + V_SPACE
        draw_mcb_pygame(screen, CCOL1_X, y, "F4", panel.state['dc_ok'], pathEnergized)
        draw_line_pygame(screen, CCOL1_X, BUS_Y_TOP, CCOL1_X, y, pathEnergized, COLOR_DC_POS)
        currentY = y + 28
        # KTC NO Contact
        y = currentY + V_SPACE
        ktc_no_open = (panel.state['ktc_state'] != 'ENERGIZED')
        pathEnergized = pathEnergized and not ktc_no_open # Path continues if KTC NO is closed (KTC Energized)
        draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "KTC NO(TC OK)", ktc_no_open, True, pathEnergized)
        draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, panel.state['dc_ok'])
        currentY = y + COMP_HEIGHT / 2
        # ... Rest of the closing circuit drawing ...
        y = currentY + V_SPACE; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "S6 Remote", False, False, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; k1_no_open = (panel.state['k1_state'] != 'ENERGIZED'); pathEnergized = pathEnergized and not k1_no_open; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "K1 NO", k1_no_open, True, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or panel.state['k1_state'] == 'ENERGIZED'); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; pathEnergized = pathEnergized and panel.state['breaker_in_service']; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "SR2 Svc", not panel.state['breaker_in_service'], True, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or panel.state['breaker_in_service']); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; pathEnergized = pathEnergized and panel.state['bus_not_earthed']; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "Bus !Earth", not panel.state['bus_not_earthed'], True, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or panel.state['bus_not_earthed']); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; pathEnergized = pathEnergized and panel.state['bus_voltage_healthy']; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "Bus V OK", not panel.state['bus_voltage_healthy'], True, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or panel.state['bus_voltage_healthy']); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; pathEnergized = pathEnergized and panel.state['buscoupler_interlock_closed']; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "B/C NC", not panel.state['buscoupler_interlock_closed'], False, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or panel.state['buscoupler_interlock_closed']); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; k86_nc_open = (panel.state['k86_state'] == 'LATCHED'); pathEnergized = pathEnergized and not k86_nc_open; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "K86 NC", k86_nc_open, False, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or not k86_nc_open); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; k94_nc_open = (panel.state['k94_state'] == 'ENERGIZED'); pathEnergized = pathEnergized and not k94_nc_open; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "K94 NC", k94_nc_open, False, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or not k94_nc_open); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; cb_nc_open = (panel.state['breaker_state'] == 'CLOSED'); pathEnergized = pathEnergized and not cb_nc_open; draw_contact_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "52b NC", cb_nc_open, False, pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or not cb_nc_open); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; pathEnergized = pathEnergized and panel.state['spring_charged']; draw_text_label_pygame(screen, CCOL1_X, y + 4, f"Spring { 'Ch.' if panel.state['spring_charged'] else 'Not Ch.'}", color=GREEN if panel.state['spring_charged'] else RED, energized=pathEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized or panel.state['spring_charged']); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE; ccEnergized = pathEnergized and panel.state['breaker_state'] == 'CLOSING'; draw_coil_pygame(screen, CCOL1_X, y - COMP_HEIGHT / 2, "CC", ccEnergized); draw_line_pygame(screen, CCOL1_X, currentY, CCOL1_X, y - COMP_HEIGHT / 2, pathEnergized);
        f5_cc_y = y + V_SPACE; draw_mcb_pygame(screen, CCOL1_X, f5_cc_y, "F5(CC)", panel.state['dc_ok'], ccEnergized); draw_line_pygame(screen, CCOL1_X, y + COMP_HEIGHT / 2, CCOL1_X, f5_cc_y, ccEnergized); draw_line_pygame(screen, CCOL1_X, f5_cc_y + 28, CCOL1_X, BUS_Y_BOTTOM, ccEnergized, COLOR_DC_NEG);

        # --- Tripping Circuit (Col 2) ---
        # ... (Draw F6, Parallel Contacts, 52a, TC1, F7 as per previous logic, using _pygame functions) ...
        draw_title(screen, "Tripping Circuit", CCOL2_X, BUS_Y_TOP - 25);
        y = BUS_Y_TOP + V_SPACE; anyDirectTripInputActive = (panel.state['trip_signal_manual_s2'] or panel.state['trip_signal_k2'] or panel.state['trip_signal_kt'] or panel.state['trip_signal_sync'] or panel.state['trip_signal_uv'] or panel.state['trip_signal_bf'] or panel.state['trip_signal_k86_no']); tripInitialPath = panel.state['dc_ok'] and anyDirectTripInputActive;
        draw_mcb_pygame(screen, CCOL2_X, y, "F6", panel.state['dc_ok'], tripInitialPath); draw_line_pygame(screen, CCOL2_X, BUS_Y_TOP, CCOL2_X, y, tripInitialPath, COLOR_DC_POS); currentY = y + 28;
        contactY = currentY + V_SPACE * 0.4; contactX = CCOL2_X; contactSpacing = V_SPACE * 0.9; anyTripInputActive = False;
        draw_line_pygame(screen, contactX, currentY, contactX, contactY + contactSpacing * 6.5, tripInitialPath); # Common bus

        draw_contact_pygame(screen, contactX, contactY, "K2 Rmt", not panel.state['trip_signal_k2'], True, panel.state['trip_signal_k2'])
        if panel.state['trip_signal_k2']:
            anyTripInputActive = True
        contactY += contactSpacing

        draw_contact_pygame(screen, contactX, contactY, "B/C KT", not panel.state['trip_signal_kt'], True, panel.state['trip_signal_kt'])
        if panel.state['trip_signal_kt']:
            anyTripInputActive = True
        contactY += contactSpacing

        draw_contact_pygame(screen, contactX, contactY, "B/C Sync", not panel.state['trip_signal_sync'], True, panel.state['trip_signal_sync'])
        if panel.state['trip_signal_sync']:
            anyTripInputActive = True
        contactY += contactSpacing

        draw_contact_pygame(screen, contactX, contactY, "S2 Trip", not panel.state['trip_signal_manual_s2'], True, panel.state['trip_signal_manual_s2'])
        if panel.state['trip_signal_manual_s2']:
            anyTripInputActive = True
        contactY += contactSpacing

        draw_contact_pygame(screen, contactX, contactY, "P127 UV", not panel.state['trip_signal_uv'], True, panel.state['trip_signal_uv'])
        if panel.state['trip_signal_uv']:
            anyTripInputActive = True
        contactY += contactSpacing

        draw_contact_pygame(screen, contactX, contactY, "50BF", not panel.state['trip_signal_bf'], True, panel.state['trip_signal_bf'])
        if panel.state['trip_signal_bf']:
            anyTripInputActive = True
        contactY += contactSpacing

        draw_contact_pygame(screen, contactX, contactY, "K86 NO", not panel.state['trip_signal_k86_no'], True, panel.state['trip_signal_k86_no'])
        if panel.state['trip_signal_k86_no']:
            anyTripInputActive = True

        commonOutY = contactY + COMP_HEIGHT / 2; draw_line_pygame(screen, contactX, commonOutY - contactSpacing * 6.5, contactX, commonOutY, anyTripInputActive); currentY = commonOutY + V_SPACE * 0.5;
        y = currentY + V_SPACE * 0.5; cb_a_open = (panel.state['breaker_state'] != 'CLOSED'); pathAfterParallel = panel.state['dc_ok'] and anyTripInputActive; draw_contact_pygame(screen, contactX, y - COMP_HEIGHT / 2, "52a NO", cb_a_open, True, pathAfterParallel and not cb_a_open); draw_line_pygame(screen, contactX, currentY, contactX, y - COMP_HEIGHT / 2, pathAfterParallel); currentY = y + COMP_HEIGHT / 2; pathEnergized = pathAfterParallel and not cb_a_open;
        y = currentY + V_SPACE; tc1_active_flag = pathEnergized; panel.state['trip_path_active_tc1'] = tc1_active_flag # Update state for potential future use
        draw_coil_pygame(screen, contactX, y - COMP_HEIGHT / 2, "TC1", tc1_active_flag); draw_line_pygame(screen, contactX, currentY, contactX, y - COMP_HEIGHT / 2, pathEnergized); currentY = y + COMP_HEIGHT / 2;
        y = currentY + V_SPACE * 0.5; draw_mcb_pygame(screen, contactX, y, "F7", panel.state['dc_ok'], tc1_active_flag); draw_line_pygame(screen, contactX, currentY, contactX, y, tc1_active_flag); draw_line_pygame(screen, contactX, y + 28, contactX, BUS_Y_BOTTOM, tc1_active_flag, COLOR_DC_NEG);


        # --- K86 Circuit (Col 3) ---
        # ... (Draw F8, P127 RL1 || K64 REF -> K86 Coil as per previous logic, using _pygame functions) ...
        draw_title(screen, "K86 Circuit", CCOL3_X, BUS_Y_TOP - 25);
        y = BUS_Y_TOP + V_SPACE; k86PathStartActive = panel.state['dc_ok'] and panel.state['trip_signal_protection']; draw_mcb_pygame(screen, CCOL3_X, y, "F8", panel.state['dc_ok'], k86PathStartActive); draw_line_pygame(screen, CCOL3_X, BUS_Y_TOP, CCOL3_X, y, k86PathStartActive, COLOR_DC_POS); currentY = y + 28;
        y = currentY + V_SPACE * 0.8; k86InputPathActive = panel.state['dc_ok'] and panel.state['trip_signal_protection']; k86InputX = CCOL3_X; p127X = k86InputX - 20; k64X = k86InputX + 20;
        draw_line_pygame(screen, k86InputX, currentY, k86InputX, y, k86InputPathActive); draw_line_pygame(screen, k86InputX, y, p127X, y, k86InputPathActive); draw_line_pygame(screen, k86InputX, y, k64X, y, k86InputPathActive);
        draw_contact_pygame(screen, p127X, y, "P127 RL1", not panel.state['trip_signal_protection'], True, k86InputPathActive); draw_contact_pygame(screen, k64X, y, "K64 REF", not panel.state['trip_signal_protection'], True, k86InputPathActive);
        k86CombineY = y + COMP_HEIGHT + 10; draw_line_pygame(screen, p127X, y + COMP_HEIGHT, p127X, k86CombineY, k86InputPathActive); draw_line_pygame(screen, k64X, y + COMP_HEIGHT, k64X, k86CombineY, k86InputPathActive); draw_line_pygame(screen, p127X, k86CombineY, k64X, k86CombineY, k86InputPathActive); currentY = k86CombineY;
        y = currentY + V_SPACE * 0.8; k86CoilEnergized = k86InputPathActive; draw_coil_pygame(screen, k86InputX, y - COMP_HEIGHT / 2, "K86 Coil", k86CoilEnergized); draw_line_pygame(screen, k86InputX, currentY, k86InputX, y- COMP_HEIGHT / 2, k86CoilEnergized); draw_line_pygame(screen, k86InputX, y + COMP_HEIGHT / 2, k86InputX, BUS_Y_BOTTOM, k86CoilEnergized, COLOR_DC_NEG);


        # --- K1 / Aux Relays (Col 4) ---
        # ... (Draw K1, KTC, K94 circuits as per previous logic, using _pygame functions) ...
        draw_title(screen, "K1 / Aux Relays", CCOL4_X, BUS_Y_TOP - 25)
        currentY = BUS_Y_TOP + V_SPACE  # Reset Y
        K1_COIL_Y = currentY + V_SPACE
        draw_coil_pygame(screen, CCOL4_X, K1_COIL_Y - COMP_HEIGHT / 2, "K1 Coil", panel.state['k1_state'] == 'ENERGIZED')
        draw_contact_pygame(screen, CCOL4_X, K1_COIL_Y - V_SPACE, "Remote Cmd", not panel.state['remote_close_command_active'], True, panel.state['dc_ok'] and panel.state['remote_close_command_active'])
        draw_line_pygame(screen, CCOL4_X, BUS_Y_TOP, CCOL4_X, K1_COIL_Y - V_SPACE, panel.state['dc_ok'] and panel.state['remote_close_command_active'], COLOR_DC_POS)
        draw_line_pygame(screen, CCOL4_X, K1_COIL_Y - V_SPACE + COMP_HEIGHT, CCOL4_X, K1_COIL_Y - COMP_HEIGHT / 2, panel.state['dc_ok'] and panel.state['remote_close_command_active'])
        draw_line_pygame(screen, CCOL4_X, K1_COIL_Y + COMP_HEIGHT / 2, CCOL4_X, BUS_Y_BOTTOM, panel.state['k1_state'] == 'ENERGIZED', COLOR_DC_NEG)
        currentY = K1_COIL_Y + COMP_HEIGHT/2 + V_SPACE
        KTC_COIL_Y = currentY
        draw_coil_pygame(screen, CCOL4_X, KTC_COIL_Y - COMP_HEIGHT / 2, "KTC Coil", panel.state['ktc_state'] == 'ENERGIZED')
        draw_contact_pygame(screen, CCOL4_X, KTC_COIL_Y - V_SPACE, "P127 RL2", not panel.state['tc_healthy'], True, panel.state['dc_ok'] and panel.state['tc_healthy'])
        draw_line_pygame(screen, CCOL4_X, BUS_Y_TOP, CCOL4_X, KTC_COIL_Y - V_SPACE, panel.state['dc_ok'] and panel.state['tc_healthy'], COLOR_DC_POS)
        draw_line_pygame(screen, CCOL4_X, KTC_COIL_Y - V_SPACE + COMP_HEIGHT, CCOL4_X, KTC_COIL_Y - COMP_HEIGHT / 2, panel.state['dc_ok'] and panel.state['tc_healthy'])
        draw_line_pygame(screen, CCOL4_X, KTC_COIL_Y + COMP_HEIGHT / 2, CCOL4_X, BUS_Y_BOTTOM, panel.state['ktc_state'] == 'ENERGIZED', COLOR_DC_NEG)
        currentY += V_SPACE * 2
        K94_COIL_Y = currentY
        k94CoilEnergized = (panel.state['breaker_state'] == 'CLOSED' and panel.state['dc_ok'])
        draw_coil_pygame(screen, CCOL4_X, K94_COIL_Y - COMP_HEIGHT / 2, "K94 Coil", k94CoilEnergized)
        draw_contact_pygame(screen, CCOL4_X, K94_COIL_Y - V_SPACE, "52a NO", panel.state['breaker_state'] != 'CLOSED', True, k94CoilEnergized)
        draw_line_pygame(screen, CCOL4_X, BUS_Y_TOP, CCOL4_X, K94_COIL_Y - V_SPACE, k94CoilEnergized, COLOR_DC_POS)
        draw_line_pygame(screen, CCOL4_X, K94_COIL_Y - V_SPACE + COMP_HEIGHT, CCOL4_X, K94_COIL_Y - COMP_HEIGHT / 2, k94CoilEnergized)
        draw_line_pygame(screen, CCOL4_X, K94_COIL_Y + COMP_HEIGHT / 2, CCOL4_X, BUS_Y_BOTTOM, k94CoilEnergized, COLOR_DC_NEG)


        # --- KDC (Col 5) ---
        # ... (Draw KDC as per previous logic, using _pygame functions) ...
        draw_title(screen, "DC Supervision", CCOL5_X, BUS_Y_TOP - 25)
        KDC_Y = BUS_Y_TOP + V_SPACE * 2
        KDC_W = 45
        KDC_H = 35
        kdcFill = GREEN_LIGHT if panel.state['kdc_state'] == 'ENERGIZED' else GRAY_MEDIUM
        kdc_rect = pygame.Rect(CCOL5_X - KDC_W / 2, KDC_Y, KDC_W, KDC_H)
        pygame.draw.rect(screen, kdcFill, kdc_rect)
        pygame.draw.rect(screen, GRAY_DARK, kdc_rect, 1)
        kdc_text = SMALL_FONT.render("KDC", True, BLACK)
        screen.blit(kdc_text, (kdc_rect.centerx - kdc_text.get_width()//2, kdc_rect.centery - kdc_text.get_height()//2))
        draw_line_pygame(screen, CCOL5_X, BUS_Y_TOP, CCOL5_X, KDC_Y, panel.state['dc_ok'], COLOR_DC_POS)
        draw_line_pygame(screen, CCOL5_X, KDC_Y + KDC_H, CCOL5_X, BUS_Y_BOTTOM, panel.state['dc_ok'], COLOR_DC_NEG)
        draw_text_label_pygame(screen, CCOL5_X, KDC_Y + KDC_H + 14, "(DC Fail Relay)")


        # --- Debug Rectangle END ---
        pygame.draw.rect(screen, RED, (25, 5, 10, 10)) # Red debug rect

    except Exception as e:
        print(f"Error during drawSchematic: {e}")
        # Optionally draw error on screen
        error_surf = DEFAULT_FONT.render(f"Drawing Error: {e}", True, RED)
        screen.blit(error_surf, (10, SCREEN_HEIGHT - 30))

# --- Pygame Specific Drawing Helpers ---
# (These wrap the core drawing logic with Pygame functions)
def draw_line_pygame(screen, x1, y1, x2, y2, energized, color=GRAY_LIGHT, width=1.5):
    line_color = ORANGE if energized else color
    line_width = int(width + 1) if energized else int(width)
    pygame.draw.line(screen, line_color, (x1, y1), (x2, y2), line_width)

def draw_contact_pygame(screen, x, y, label, isOpen, isNormallyOpen=True, energized=False):
    length = 20
    gap = 5
    font = SMALL_FONT
    # Connections
    draw_line_pygame(screen, x - length / 2, y + COMP_HEIGHT / 2, x, y + COMP_HEIGHT / 2, energized)
    draw_line_pygame(screen, x + length, y + COMP_HEIGHT / 2, x + length + length / 2, y + COMP_HEIGHT / 2, energized)
    # Symbol parts
    line_color = GREEN if energized and not isOpen else (RED if energized and isOpen else GRAY_DARK)
    pygame.draw.line(screen, line_color, (x, y), (x, y + COMP_HEIGHT), 2) # Fixed part
    if isNormallyOpen:
        if isOpen:
            pygame.draw.line(screen, line_color, (x + gap, y), (x + length, y + COMP_HEIGHT / 2), 2)
        else:
            pygame.draw.line(screen, line_color, (x, y + COMP_HEIGHT / 2), (x + length, y + COMP_HEIGHT / 2), 2)
    else: # NC
        if isOpen:
            pygame.draw.line(screen, line_color, (x + gap, y + COMP_HEIGHT / 2), (x + length, y + COMP_HEIGHT), 2)
        else:
            pygame.draw.line(screen, line_color, (x, y + COMP_HEIGHT / 2), (x + length, y + COMP_HEIGHT / 2), 2) # Closed bar
            pygame.draw.line(screen, line_color, (x + gap, y), (x + length, y + COMP_HEIGHT), 1) # NC slash
    # Label
    text_surf = font.render(label, True, BLACK)
    screen.blit(text_surf, (x + length + 6, y + COMP_HEIGHT / 2 - text_surf.get_height() // 2))

def draw_coil_pygame(screen, x, y, label, energized):
    radius = COMP_HEIGHT / 2 + 1
    font = SMALL_FONT
    coil_color = ORANGE if energized else GRAY_MEDIUM
    pygame.draw.circle(screen, coil_color, (x, y + radius), radius)
    pygame.draw.circle(screen, BLACK, (x, y + radius), radius, 1) # Outline
    text_surf = font.render(label, True, BLACK)
    screen.blit(text_surf, (x - text_surf.get_width() // 2, y + COMP_HEIGHT + 5))

def draw_mcb_pygame(screen, x, y, label, closed, energized=False):
    width = 16
    height = 28
    font = SMALL_FONT
    rect = pygame.Rect(x - width / 2, y, width, height)
    line_color = ORANGE if energized else GRAY_DARK
    pygame.draw.rect(screen, line_color, rect, 2)
    diag_color = GREEN if closed else RED
    if closed:
        pygame.draw.line(screen, diag_color, (rect.left, rect.top + 6), (rect.right, rect.bottom - 6), 2)
    else:
        pygame.draw.line(screen, diag_color, (rect.left, rect.centery), (rect.right, rect.centery), 2)
    text_surf = font.render(label, True, BLACK)
    screen.blit(text_surf, (x - text_surf.get_width() // 2, y - text_surf.get_height() - 2))

def draw_bus_pygame(screen, y, label, color=GRAY_DARK, x_start=BUS_X_START_CTRL, x_end=BUS_X_END_CTRL):
    pygame.draw.rect(screen, color, (x_start, y - 4, x_end - x_start, 8))
    text_surf = LABEL_FONT.render(label, True, BLACK)
    screen.blit(text_surf, (x_start + 8, y - text_surf.get_height() - 6))

def draw_breaker_symbol_pygame(screen, x, y, stateObj, isPowerCircuit=False):
    width = 55 if isPowerCircuit else 32
    height = 85 if isPowerCircuit else 55
    font = LABEL_FONT
    rect = pygame.Rect(x - width / 2, y, width, height)
    pygame.draw.rect(screen, BLACK, rect, 3 if isPowerCircuit else 2)
    text_surf = font.render("CB", True, BLACK)
    screen.blit(text_surf, (rect.centerx - text_surf.get_width() // 2, rect.top - text_surf.get_height() - 2))
    contactYtop = rect.top + 6
    contactYbottom = rect.bottom - 6
    contactMidGap = 6
    line_width = 5 if isPowerCircuit else 4
    if stateObj['breaker_state'] == 'CLOSED':
        pygame.draw.line(screen, RED, (x, contactYtop), (x, contactYbottom), line_width)
    else:
        pygame.draw.line(screen, CYAN_LIGHT, (x, contactYtop), (x, rect.centery - contactMidGap), line_width)
        pygame.draw.line(screen, CYAN_LIGHT, (x, rect.centery + contactMidGap), (x, contactYbottom), line_width)

def draw_text_label_pygame(screen, x, y, text, color=BLACK, font=SMALL_FONT, align='center', energized=False):
    text_color = ORANGE if energized else color
    text_surf = font.render(text, True, text_color)
    text_rect = text_surf.get_rect()
    if align == 'center':
        text_rect.center = (x, y)
    elif align == 'left':
        text_rect.midleft = (x, y)
    else:
        text_rect.midright = (x, y) # Default right or specify more
    screen.blit(text_surf, text_rect)

def draw_title(screen, text, x, y):
     title_surf = TITLE_FONT.render(text, True, GRAY_DARK)
     screen.blit(title_surf, (x - title_surf.get_width() // 2, y))

# --- Button Definition ---
buttons = {} # Dictionary to store button rects and actions

def create_button(x, y, w, h, text, action_func, action_args=None):
    rect = pygame.Rect(x, y, w, h)
    buttons[text] = {'rect': rect, 'action': action_func, 'args': action_args or []}
    return rect

def draw_buttons(screen):
    button_font = DEFAULT_FONT
    for text, data in buttons.items():
        rect = data['rect']
        # Basic button appearance
        pygame.draw.rect(screen, GRAY_LIGHT, rect, border_radius=5)
        pygame.draw.rect(screen, GRAY_DARK, rect, 1, border_radius=5)
        text_surf = button_font.render(text, True, BLACK)
        screen.blit(text_surf, (rect.centerx - text_surf.get_width() // 2, rect.centery - text_surf.get_height() // 2))

def check_button_clicks(panel, pos):
    for text, data in buttons.items():
        if data['rect'].collidepoint(pos):
            print(f"Button '{text}' clicked")
            action = data['action']
            args = data['args']
            # Special handling for trip commands needing source name
            if action == panel.trip_command_direct:
                 if args: # Expecting flag name and readable name
                      flag_name = args[0]
                      readable_name = args[1]
                      if panel.initiate_direct_trip(flag_name, readable_name):
                           # Start timer/delay if needed for visual effect in main loop
                           pass
            elif action == panel.initiate_protection_trip:
                 panel.initiate_protection_trip()
            elif action == panel.toggle_k1:
                 if panel.toggle_k1(): # Returns true if close attempt started
                      # Start K1 pulse timer/logic in main loop if needed
                      pass
            else: # Other toggles/resets
                 action(*args) # Call function directly
            return True # Click handled
    return False

# --- Main Simulation Loop ---
def main():
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("11kV Incomer Simulation - Visual")
    clock = pygame.time.Clock()

    panel = SwitchgearPanel()

    # --- Define Button Areas (Example - Adjust positions/sizes as needed) ---
    button_w, button_h = 180, 35
    button_x_start = POWER_CIRCUIT_WIDTH + (CONTROL_CIRCUIT_X_START - POWER_CIRCUIT_WIDTH - button_w) // 2 # Center between power/control
    button_y_start = SCREEN_HEIGHT - 150
    button_y_step = 45

    # Clear previous buttons if any
    buttons.clear()
    # create_button(button_x_start, button_y_start, button_w, button_h, "Close (K1)", panel.toggle_k1) # Now uses toggle
    # create_button(button_x_start, button_y_start + button_y_step, button_w, button_h, "Trip (S2)", panel.trip_command_direct, ['trip_signal_s2', 'S2'])
    # create_button(button_x_start, button_y_start + 2*button_y_step, button_w, button_h, "Prot. Trip (K86)", panel.initiate_protection_trip)
    # create_button(button_x_start, button_y_start + 3*button_y_step, button_w, button_h, "Reset K86", panel.reset_k86)
    # create_button(button_x_start, button_y_start + 4*button_y_step, button_w, button_h, "Reset Sim", panel.reset_simulation)
    # Need to map HTML buttons to Pygame Rects and actions

    running = True
    while running:
        # --- Event Handling ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left mouse button
                    # Check if click is on any defined button
                    check_button_clicks(panel, event.pos)
                    # Placeholder: Need to map clicks to the panel methods based on button rects

        # --- Update State (Based on time, previous actions etc.) ---
        # e.g., Handle delays for closing/tripping animations if implemented
        # e.g., End K1 pulse after timeout

        # --- Update dependent states (ensure consistency) ---
        panel._update_dependent_states()

        # --- Drawing ---
        draw_schematic(screen, panel)
        # draw_buttons(screen) # Draw the buttons

        # --- Update Display ---
        pygame.display.flip()

        # --- Frame Rate Control ---
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()