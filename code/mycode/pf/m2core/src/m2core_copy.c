/*
 * Viewer (M5stack Core2) driver main source file
 * Modified for larger grid and MQTT/WiFi severity overlay
 * - Grid covers ±100 m around center lat/lon
 * - Each cell represents ~10 m
 * - Incoming (lat, lon, severity) updates cell color
 * - Includes fake test coordinates on startup, including all four corners
 */

#include <zephyr/device.h>
#include <zephyr/drivers/display.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <lvgl.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/hci.h>
#include <zephyr/sys/byteorder.h>
#include <string.h>
#include <math.h>
#include <zephyr/data/json.h>
#include <myconfig.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/printk.h>

#define NUM_OF_SENSORS 2
#define BLOCK_SIZE    11

extern const lv_img_dsc_t bounds;

LOG_MODULE_REGISTER(viewer, CONFIG_LOG_DEFAULT_LEVEL);

#define SCREEN_WIDTH   320
#define SCREEN_HEIGHT  240
#define GRID_SPAN_M_Y   75     /* ±75 m vertically (latitude) */
#define GRID_SPAN_M_X   100    /* ±100 m horizontally (longitude) */
#define CELL_SIZE_M     10     /* 10 m per cell */
#define ROWS            ((GRID_SPAN_M_Y * 2) / CELL_SIZE_M + 1)  /* 150/10+1=16 */
#define COLS            ((GRID_SPAN_M_X * 2) / CELL_SIZE_M + 1)  /* 200/10+1=21 */
#define M_PI         3.14159265358979323846f

/* Center cell indices */
static const int CENTER_ROW = ROWS / 2;
static const int CENTER_COL = COLS / 2;
/* Meters per cell */
static const float METERS_PER_CELL_Y = (2.0f * GRID_SPAN_M_Y) / ROWS;
static const float METERS_PER_CELL_X = (2.0f * GRID_SPAN_M_X) / COLS;


/* Geographic center */
static const float CENTER_LAT = -27.499964;
static const float CENTER_LON = 153.014639f;

/* Conversion factors */
static const float LAT_DEG_PER_M = 1.0f / 111000.0f;
static float LON_DEG_PER_M;

/* Pre-calc cell pixel size */
static int cell_w, cell_h;

static const char* base_uuid = BASE_UUID;

/* Persistent arrays for line endpoints */
static lv_point_t vline_pts[COLS + 1][2];
static lv_point_t hline_pts[ROWS + 1][2];

struct BleJSON {
    float lat;
    float lon;
    int   severity;
};

static const struct json_obj_descr ble_descr[] = {
    JSON_OBJ_DESCR_PRIM(struct BleJSON, lat,      JSON_TOK_FLOAT),
    JSON_OBJ_DESCR_PRIM(struct BleJSON, lon,      JSON_TOK_FLOAT),
    JSON_OBJ_DESCR_PRIM(struct BleJSON, severity, JSON_TOK_INT64),
};

static void draw_grid(void) {
    cell_w = SCREEN_WIDTH / COLS;
    cell_h = SCREEN_HEIGHT / ROWS;
    for (int i = 0; i <= COLS; i++) {
        vline_pts[i][0] = (lv_point_t){ .x = i * cell_w, .y = 0 };
        vline_pts[i][1] = (lv_point_t){ .x = i * cell_w, .y = SCREEN_HEIGHT };
        lv_obj_t *ln = lv_line_create(lv_scr_act());
        lv_line_set_points(ln, vline_pts[i], 2);
        lv_obj_set_style_line_color(ln, lv_color_black(), 0);
        lv_obj_set_style_line_width(ln, 0, 0);
    }
    for (int i = 0; i <= ROWS; i++) {
        hline_pts[i][0] = (lv_point_t){ .x = 0, .y = i * cell_h };
        hline_pts[i][1] = (lv_point_t){ .x = SCREEN_WIDTH, .y = i * cell_h };
        lv_obj_t *ln = lv_line_create(lv_scr_act());
        lv_line_set_points(ln, hline_pts[i], 2);
        lv_obj_set_style_line_color(ln, lv_color_black(), 0);
        lv_obj_set_style_line_width(ln, 0, 0);
    }
}

static void color_cell(int row, int col, int severity) {
    if (row < 0) row = 0;
    if (row >= ROWS) row = ROWS - 1;
    if (col < 0) col = 0;
    if (col >= COLS) col = COLS - 1;
    lv_obj_t *cell = lv_obj_create(lv_scr_act());
    lv_obj_set_size(cell, cell_w - 2, cell_h - 2);
    lv_color_t c = (severity <= 0 ? lv_color_hex(0x00FF00)
                      : (severity == 1 ? lv_color_hex(0xFFFF00)
                                       : lv_color_hex(0xFF0000)));
    lv_obj_set_style_bg_color(cell, c, 0);
    lv_obj_set_style_border_width(cell, 0, 0);
    lv_obj_set_pos(cell, col * cell_w + 1, row * cell_h + 1);
}

static void update_from_geo(float lat, float lon, int severity) {
    float dlat = lat - CENTER_LAT;
    float dlon = lon - CENTER_LON;
    float dy_m = dlat / LAT_DEG_PER_M;
    float dx_m = dlon / LON_DEG_PER_M;
    int row = CENTER_ROW - (int)roundf(dy_m / METERS_PER_CELL_Y);
    int col = CENTER_COL + (int)roundf(dx_m / METERS_PER_CELL_X);
    color_cell(row, col, severity);
}

static void device_found(const bt_addr_le_t *addr,
                         int8_t rssi,
                         uint8_t type,
                         struct net_buf_simple *ad) {

    if (ad->len < (2 + UUID_SIZE)) {
        return;
    }

    char name[7];
	for (int i = 2; i < (2 + UUID_SIZE); i++) {
        name[i - 2] = ad->data[i];
    }
    name[6] = '\0';

    if (strcmp(name, base_uuid) == 0) {
        for (int i = 8; i < (8 + (11 * 2)); i += 11) {
            uint8_t  id      = ad[11 * i];
            uint8_t  stopped = ad[(11 * i) + 1];
            int32_t  lat_i   = ad->data[(11 * i) + 2] | (ad->data[(11 * i) + 3] << 8) |
				                (ad->data[(11 * i) + 4] << 16) | (ad->data[(11 * i) + 5] << 24);
            int32_t  lon_i   = ad->data[(11 * i) + 6] | (ad->data[(11 * i) + 7] << 8) |
				                (ad->data[(11 * i) + 8] << 16) | (ad->data[(11 * i) + 9] << 24);
            uint8_t  sev     = ad[(11 * i) + 10];

            float lat = lat_i / 1e6f;
            float lon = lon_i / 1e6f;

            printk("Sensor %u: id=%u stopped=%u lat=%f lon=%f sev=%u\n",
                i, id, stopped, lat, lon, sev);

            update_from_geo(lat, lon, sev);
        }
    }
}

int main(void) {
    const struct device *disp = DEVICE_DT_GET(DT_CHOSEN(zephyr_display));
    if (!device_is_ready(disp)) {
        LOG_ERR("Display not ready");
        return -ENODEV;
    }
    LON_DEG_PER_M = 1.0f / (111000.0f * cosf(CENTER_LAT * M_PI / 180.0f));
    lv_init();
    lv_obj_clean(lv_scr_act());
    draw_grid();
    display_blanking_off(disp);

    lv_obj_t *bg_img = lv_img_create(lv_scr_act());
    lv_img_set_src(bg_img, &bounds); // Use the variable name from bounds.c
    lv_obj_set_size(bg_img, SCREEN_WIDTH, SCREEN_HEIGHT);
    lv_obj_set_pos(bg_img, 0, 0);
    lv_obj_move_background(bg_img);

    float lat_north = CENTER_LAT + (GRID_SPAN_M_Y * LAT_DEG_PER_M);
    float lat_south = CENTER_LAT - (GRID_SPAN_M_Y * LAT_DEG_PER_M);
    float lon_east  = CENTER_LON + (GRID_SPAN_M_X * LON_DEG_PER_M);
    float lon_west  = CENTER_LON - (GRID_SPAN_M_X * LON_DEG_PER_M);

    update_from_geo(lat_north, lon_west, 1);
    update_from_geo(lat_north, lon_east, 1);
    update_from_geo(lat_south, lon_west, 1);
    update_from_geo(lat_south, lon_east, 1);

    /* Enable Bluetooth scanning */
    int err = bt_enable(NULL);
    if (err) {
        LOG_ERR("BT init failed (%d)", err);
        return 0;
    }
    struct bt_le_scan_param sp = {
        .type    = BT_LE_SCAN_TYPE_PASSIVE,
        .options = BT_LE_SCAN_OPT_NONE,
        .interval= BT_GAP_SCAN_FAST_INTERVAL,
        .window  = BT_GAP_SCAN_FAST_WINDOW,
    };
    err = bt_le_scan_start(&sp,  device_found);
    if (err) {
        LOG_ERR("BT scan failed (%d)", err);
    } else {
        LOG_INF("BT scanning...");
    }

    while (1) {
        lv_timer_handler();
        k_msleep(10);
    }
    return 0;
}
