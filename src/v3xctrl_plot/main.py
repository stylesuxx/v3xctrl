import numpy as np
from numpy.typing import NDArray
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.table import Table
from matplotlib.axes import Axes
from typing import Dict, List, Tuple, Optional, Any


def read_s1p(
    file_path: str
) -> Tuple[NDArray[Any], NDArray[Any], float | None]:
    freqs: list[float] = []
    s11: List[float] = []
    with open(file_path, 'r') as f:
        data_format: Optional[str] = None
        freq_unit: Optional[str] = None
        z0: Optional[float] = None

        for line in f:
            if line.startswith('!') or line.strip() == '':
                continue

            if line.lower().startswith('#'):
                parts = line.lower().split()
                freq_unit = parts[1]
                data_format = parts[3]
                z0 = float(parts[5])
                continue

            values = list(map(float, line.strip().split()))
            freqs.append(values[0])
            if data_format == 'db':
                mag = 10**(values[1]/20)
                phase = np.deg2rad(values[2])
            elif data_format == 'ma':
                mag = values[1]
                phase = np.deg2rad(values[2])
            elif data_format == 'ri':
                real, imag = values[1], values[2]
                mag = np.sqrt(real**2 + imag**2)
                phase = np.arctan2(imag, real)
            else:
                raise ValueError("Unsupported format")

            s11.append(mag * np.exp(1j * phase))

    freqs_np = np.array(freqs)
    s11_np = np.array(s11)
    if freq_unit == 'hz':
        freqs_np /= 1e6
    elif freq_unit == 'khz':
        freqs_np /= 1e3
    elif freq_unit == 'ghz':
        freqs_np *= 1e3

    return freqs_np, s11_np, z0


def reflection_to_swr(s11: NDArray[Any]) -> NDArray[Any]:
    gamma = np.abs(s11)
    return (1 + gamma) / (1 - gamma)


def get_swr_color(swr: float) -> str:
    if swr <= 1.25:
        return '#00aa00'  # green
    elif swr <= 1.5:
        return '#9acd32'  # yellowgreen
    elif swr <= 2.0:
        return '#ffa500'  # orange
    else:
        return '#ff6666'  # red


def apply_band_colors_unified(table: Table, swr_values: NDArray[Any]) -> None:
    for i, swr in enumerate(swr_values):
        color = get_swr_color(swr)
        cell = table[i + 1, 0]  # +1 for header
        cell.set_facecolor(color)
        cell.set_text_props(color='black')  # type: ignore[arg-type]


lte_bands_full = {
    'B28': {
        'dl': (758, 803),
        'ul': (703, 748)
    },
    'B20': {
        'dl': (791, 821),
        'ul': (832, 862)
    },
    'B8': {
        'dl': (925, 960),
        'ul': (880, 915)
    },
    'B3':  {
        'dl': (1805, 1880),
        'ul': (1710, 1785)
    },
    'B1':  {
        'dl': (2110, 2170),
        'ul': (1920, 1980)
    },
    'B7':  {
        'dl': (2620, 2690),
        'ul': (2500, 2570)
    },
}


def plot_lte_bands_center_based(
    ax: Axes,
    band_type: str,
    band_data: Dict[str, Any],
    freqs: NDArray[Any],
    swr: NDArray[Any]
) -> None:
    for i in range(1, len(freqs)):
        if freqs[i] - freqs[i - 1] > 200:
            continue  # Skip large jumps
        ax.plot(freqs[i - 1:i + 1], swr[i - 1:i + 1], color='black', zorder=1)
    ax.axhline(2.0, color='gray', linestyle='--', zorder=1)
    ax.set_xlim(600, 2800)
    ax.set_ylim(1, 3)
    ax.set_yticks([1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0])
    ax.set_xlabel('Frequency (MHz)')
    ax.set_ylabel('SWR')
    ax.grid(True)

    label_index = 0
    for entry in band_data:
        band = entry['Band']
        center = entry['Center (MHz)']
        swr_val = entry['SWR @ Center']
        start, end = lte_bands_full[band][band_type]
        color = get_swr_color(swr_val)
        ax.axvspan(start, end, color=color, alpha=0.3, zorder=0)
        y_pos = [2.9, 2.7, 2.5, 2.3][label_index % 4]
        ax.text(center, y_pos, band, ha='center', va='top', fontsize=9, zorder=2)
        label_index += 1


if __name__ == '__main__':
    import sys
    import os

    if len(sys.argv) != 2:
        print("Usage: python swr_lte_plotter.py <file.s1p>")
        sys.exit(1)

    file_path = sys.argv[1]
    antenna_name = os.path.splitext(os.path.basename(file_path))[0]

    freqs, s11, z0 = read_s1p(file_path)
    swr = reflection_to_swr(s11)

    mask = (freqs >= 600) & (freqs <= 2800)
    freqs_filtered = freqs[mask]
    swr_filtered = swr[mask]

    def get_band_data(band_type: str) -> List[Dict[str, Any]]:
        data: List[Dict[str, Any]] = []
        for band, ranges in lte_bands_full.items():
            if band_type not in ranges:
                continue
            center = (ranges[band_type][0] + ranges[band_type][1]) / 2
            idx = np.argmin(np.abs(freqs_filtered - center))
            data.append({
                'Band': band,
                'Center (MHz)': round(center, 1),
                'SWR @ Center': round(swr_filtered[idx], 2),
            })

        return sorted(data, key=lambda x: x['SWR @ Center'])

    df_dl = pd.DataFrame(get_band_data('dl'))
    df_ul = pd.DataFrame(get_band_data('ul'))
    band_data_dl = df_dl.to_dict('records')
    band_data_ul = df_ul.to_dict('records')

    fig = plt.figure(figsize=(10, 11), dpi=100)
    gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[1, 1, 0.6])

    ax_dl = plt.subplot(gs[0, :])
    ax_dl.set_title("Downlink")
    ax_dl.text(0.5, 1.2, antenna_name, size=20, fontweight='bold', ha="center", transform=ax_dl.transAxes)
    plot_lte_bands_center_based(ax_dl, 'dl', band_data_dl, freqs_filtered, swr_filtered)

    ax_ul = plt.subplot(gs[1, :])
    ax_ul.set_title("Uplink")
    plot_lte_bands_center_based(ax_ul, 'ul', band_data_ul, freqs_filtered, swr_filtered)

    ax_table_dl = plt.subplot(gs[2, 0])
    ax_table_dl.axis('off')
    ax_table_dl.text(0.065, 1.02, "Downlink Band Summary", size=12, fontweight='bold', transform=ax_table_dl.transAxes)

    ax_table_ul = plt.subplot(gs[2, 1])
    ax_table_ul.axis('off')
    ax_table_ul.text(0.065, 1.02, "Uplink Band Summary", size=12, fontweight='bold', transform=ax_table_ul.transAxes)

    table_dl = ax_table_dl.table(
        cellText=df_dl.values,
        colLabels=df_dl.columns,
        cellLoc='left',
        loc='center',
        colWidths=[0.14, 0.35, 0.38]
    )
    table_ul = ax_table_ul.table(
        cellText=df_ul.values,
        colLabels=df_ul.columns,
        cellLoc='center',
        loc='center',
        colWidths=[0.14, 0.35, 0.38]
      )

    apply_band_colors_unified(table_dl, df_dl["SWR @ Center"].values)
    apply_band_colors_unified(table_ul, df_ul["SWR @ Center"].values)

    for table in [table_dl, table_ul]:
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.0, 1.4)

        # Bold headers
        for key, cell in table.get_celld().items():
            if key[0] == 0:  # Row 0 = header
                cell.set_text_props(weight='bold')
            if key[0] != 0:
                if key[1] == 0:
                    cell.get_text().set_ha('left')
                if key[1] == 1 or key[1] == 2:
                    cell.get_text().set_ha('right')

    plt.tight_layout()

    plt.savefig(f"{antenna_name}_SWR.png", dpi=150, bbox_inches='tight')
