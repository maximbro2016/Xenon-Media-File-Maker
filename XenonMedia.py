import os
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
import numpy as np

# --- CONFIGURATION & CONSTANTS ---
MAGIC_XMV = b"\xA3\xB2\xFE\x12"  # Compressed Video
MAGIC_XV = b"\xA3\xB2\xFE\x13"  # Uncompressed Video (720p only)
MAGIC_XVA = b"\xA3\xB2\xFE\x14"  # Audio Format
MAGIC_XMI = b"\xA3\xB2\xFE\x15"  # Image Format
MAGIC_AXMI = b"\xA3\xB2\xFE\x16"  # Animated Image Format
MAGIC_XMF = b"\xA3\xB2\xFE\x17"  # Metadata Format (.xmi with DPI)

XOR_KEY = 0x5A  # Data payload transformation key

RESOLUTIONS = {
    "480p": (854, 480),
    "540p": (960, 540),
    "720p": (1280, 720),
    "864p": (1536, 864),
    "960p": (1706, 960),
    "1080p": (1920, 1080),
}


class XenonMediaApp:

  def __init__(self, root):
    self.root = root
    self.root.title("Xenon Media Suite (Ultimate Edition)")
    self.root.geometry("650x580")
    self.root.minsize(600, 500)

    style = ttk.Style()
    style.theme_use("clam")

    # Main Notebook (Tabs)
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    # Tabs
    self.video_tab = ttk.Frame(notebook)
    self.image_tab = ttk.Frame(notebook)
    self.audio_tab = ttk.Frame(notebook)
    self.player_tab = ttk.Frame(notebook)

    notebook.add(self.video_tab, text=" Video (.xmv / .xv) ")
    notebook.add(self.image_tab, text=" Image & Animation (.xmi/.axmi/.xmf) ")
    notebook.add(self.audio_tab, text=" Audio (.xva) ")
    notebook.add(self.player_tab, text=" Universal Player ")

    self.setup_video_ui()
    self.setup_image_ui()
    self.setup_audio_ui()
    self.setup_player_ui()

  # ==================== 1. VIDEO CONVERTER TAB ====================
  def setup_video_ui(self):
    frame = ttk.LabelFrame(
        self.video_tab, text=" Video Converter (.xmv & .xv) "
    )
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ttk.Label(frame, text="Select Source Video:").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    f_frame = ttk.Frame(frame)
    f_frame.pack(fill="x", padx=10, pady=5)

    self.vid_path_var = tk.StringVar()
    ttk.Entry(f_frame, textvariable=self.vid_path_var, width=45).pack(
        side="left", fill="x", expand=True
    )
    ttk.Button(f_frame, text="Browse...", command=self.browse_video).pack(
        side="right", padx=(5, 0)
    )

    ttk.Label(frame, text="Format Type:").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    self.vid_type_var = tk.StringVar(value=".xmv")
    type_combo = ttk.Combobox(
        frame,
        textvariable=self.vid_type_var,
        values=[".xmv (Compressed - All Resolutions)", ".xv (Uncompressed - 720p Only)"],
        state="readonly",
    )
    type_combo.pack(fill="x", padx=10, pady=5)

    ttk.Label(frame, text="Target Resolution (.xmv only):").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    self.vid_res_var = tk.StringVar(value="720p")
    ttk.Combobox(
        frame,
        textvariable=self.vid_res_var,
        values=list(RESOLUTIONS.keys()),
        state="readonly",
    ).pack(fill="x", padx=10, pady=5)

    self.vid_status = ttk.Label(
        frame, text="Status: Ready", foreground="gray"
    )
    self.vid_status.pack(anchor="w", padx=10, pady=15)

    ttk.Button(
        frame, text="Convert Video", command=self.convert_video
    ).pack(fill="x", padx=10, pady=10)

  def browse_video(self):
    f = filedialog.askopenfilename(
        filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov")]
    )
    if f:
      self.vid_path_var.set(f)

  def convert_video(self):
    inp = self.vid_path_var.get()
    if not inp or not os.path.exists(inp):
      messagebox.showerror("Error", "Please select a valid source video.")
      return

    is_xv = ".xv (" in self.vid_type_var.get()
    ext = ".xv" if is_xv else ".xmv"

    out_file = filedialog.asksaveasfilename(
        defaultextension=ext, filetypes=[(f"Xenon Video ({ext})", f"*{ext}")]
    )
    if not out_file:
      return

    try:
      self.vid_status.config(
          text="Status: Processing video...", foreground="blue"
      )
      self.root.update_idletasks()

      # .xv is strictly 720p uncompressed
      if is_xv:
        width, height = RESOLUTIONS["720p"]
        magic = MAGIC_XV
      else:
        width, height = RESOLUTIONS[self.vid_res_var.get()]
        magic = MAGIC_XMV

      cap = cv2.VideoCapture(inp)
      fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

      temp_s = "temp_v.avi"
      # Use raw uncompressed fourcc for .xv if possible, or XVID for .xmv
      fourcc = (
          cv2.VideoWriter_fourcc(*"IYUV")
          if is_xv
          else cv2.VideoWriter_fourcc(*"XVID")
      )
      out = cv2.VideoWriter(temp_s, fourcc, fps, (width, height))

      while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
          break
        out.write(
            cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        )

      cap.release()
      out.release()

      with open(temp_s, "rb") as f:
        payload = f.read()

      transformed = bytearray(b ^ XOR_KEY for b in payload)
      header = (
          magic
          + struct.pack(">H", width)
          + struct.pack(">H", height)
          + struct.pack(">I", int(fps * 100))
      )

      with open(out_file, "wb") as f_out:
        f_out.write(header + transformed)

      if os.path.exists(temp_s):
        os.remove(temp_s)

      self.vid_status.config(text="Status: Success!", foreground="green")
      messagebox.showinfo("Success", f"Successfully created {ext} file!")
    except Exception as e:
      self.vid_status.config(text="Status: Failed", foreground="red")
      messagebox.showerror("Error", str(e))

  # ==================== 2. IMAGE & ANIMATION TAB ====================
  def setup_image_ui(self):
    frame = ttk.LabelFrame(
        self.image_tab, text=" Image & Animation Suite (.xmi / .axmi / .xmf) "
    )
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ttk.Label(frame, text="Select Source Image / Animation / Video:").pack(
        anchor="w", padx=10, pady=(5, 0)
    )
    f_frame = ttk.Frame(frame)
    f_frame.pack(fill="x", padx=10, pady=5)

    self.img_path_var = tk.StringVar()
    ttk.Entry(f_frame, textvariable=self.img_path_var, width=45).pack(
        side="left", fill="x", expand=True
    )
    ttk.Button(f_frame, text="Browse...", command=self.browse_image).pack(
        side="right", padx=(5, 0)
    )

    ttk.Label(frame, text="Target Type:").pack(
        anchor="w", padx=10, pady=(5, 0)
    )
    self.img_type_var = tk.StringVar(value=".xmi (Image)")
    ttk.Combobox(
        frame,
        textvariable=self.img_type_var,
        values=[
            ".xmi (Xenon Image)",
            ".axmi (Animated XMI - GIF/Video equivalent)",
            ".xmf (XMI Metadata Format with DPI)",
        ],
        state="readonly",
    ).pack(fill="x", padx=10, pady=5)

    opt_frame = ttk.Frame(frame)
    opt_frame.pack(fill="x", padx=10, pady=5)

    ttk.Label(opt_frame, text="Resolution:").pack(side="left")
    self.img_res_var = tk.StringVar(value="720p")
    ttk.Combobox(
        opt_frame,
        textvariable=self.img_res_var,
        values=list(RESOLUTIONS.keys()),
        width=10,
        state="readonly",
    ).pack(side="left", padx=5)

    ttk.Label(opt_frame, text="FPS (.axmi):").pack(side="left", padx=(10, 0))
    self.axmi_fps_var = tk.StringVar(value="30")
    ttk.Combobox(
        opt_frame,
        textvariable=self.axmi_fps_var,
        values=["30", "60"],
        width=5,
        state="readonly",
    ).pack(side="left", padx=5)

    ttk.Label(opt_frame, text="DPI (.xmf):").pack(side="left", padx=(10, 0))
    self.xmf_dpi_var = tk.StringVar(value="300")
    ttk.Combobox(
        opt_frame,
        textvariable=self.xmf_dpi_var,
        values=["72", "150", "300"],
        width=5,
        state="readonly",
    ).pack(side="left", padx=5)

    self.img_status = ttk.Label(
        frame, text="Status: Ready", foreground="gray"
    )
    self.img_status.pack(anchor="w", padx=10, pady=10)

    ttk.Button(
        frame, text="Create Xenon Media Asset", command=self.convert_image
    ).pack(fill="x", padx=10, pady=10)

  def browse_image(self):
    f = filedialog.askopenfilename(
        filetypes=[
            ("Media Files", "*.png *.jpg *.jpeg *.gif *.mp4 *.avi"),
            ("All Files", "*.*"),
        ]
    )
    if f:
      self.img_path_var.set(f)

  def convert_image(self):
    inp = self.img_path_var.get()
    if not inp or not os.path.exists(inp):
      messagebox.showerror("Error", "Please select a source file.")
      return

    selection = self.img_type_var.get()
    if ".xmi (" in selection:
      ext, magic = ".xmi", MAGIC_XMI
    elif ".axmi (" in selection:
      ext, magic = ".axmi", MAGIC_AXMI
    else:
      ext, magic = ".xmf", MAGIC_XMF

    out_file = filedialog.asksaveasfilename(
        defaultextension=ext, filetypes=[(f"Xenon Format ({ext})", f"*{ext}")]
    )
    if not out_file:
      return

    try:
      self.img_status.config(
          text="Status: Encoding asset...", foreground="blue"
      )
      self.root.update_idletasks()

      w, h = RESOLUTIONS[self.img_res_var.get()]

      if ext == ".axmi":
        # Animated XMI processing
        cap = cv2.VideoCapture(inp)
        fps = float(self.axmi_fps_var.get())
        temp_s = "temp_ax.avi"
        out = cv2.VideoWriter(
            temp_s,
            cv2.VideoWriter_fourcc(*"XVID"),
            fps,
            (w, h),
        )
        while cap.isOpened():
          ret, frame = cap.read()
          if not ret:
            break
          out.write(cv2.resize(frame, (w, h)))
        cap.release()
        out.release()

        with open(temp_s, "rb") as f:
          payload = f.read()
        os.remove(temp_s)

        header = (
            magic
            + struct.pack(">H", w)
            + struct.pack(">H", h)
            + struct.pack(">B", int(fps))
        )
      else:
        # Static Image or Metadata (.xmi / .xmf)
        img = cv2.imread(inp)
        if img is None:
          # Try reading via video first frame if image read fails
          cap = cv2.VideoCapture(inp)
          ret, img = cap.read()
          cap.release()
          if img is None:
            raise ValueError("Could not read image source.")

        resized = cv2.resize(img, (w, h))
        success, encoded_img = cv2.imencode(".png", resized)
        payload = bytearray(encoded_img)

        header = magic + struct.pack(">H", w) + struct.pack(">H", h)
        if ext == ".xmf":
          dpi = int(self.xmf_dpi_var.get())
          header += struct.pack(">H", dpi)  # Embed DPI metadata

      transformed = bytearray(b ^ XOR_KEY for b in payload)
      with open(out_file, "wb") as f_out:
        f_out.write(header + transformed)

      self.img_status.config(text="Status: Success!", foreground="green")
      messagebox.showinfo("Success", f"Successfully created {ext} file!")
    except Exception as e:
      self.img_status.config(text="Status: Failed", foreground="red")
      messagebox.showerror("Error", str(e))

  # ==================== 3. AUDIO CONVERTER TAB ====================
  def setup_audio_ui(self):
    frame = ttk.LabelFrame(self.audio_tab, text=" Xenon Audio Converter (.xva) ")
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ttk.Label(frame, text="Select Source Audio/Video File:").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    f_frame = ttk.Frame(frame)
    f_frame.pack(fill="x", padx=10, pady=5)

    self.aud_path_var = tk.StringVar()
    ttk.Entry(f_frame, textvariable=self.aud_path_var, width=45).pack(
        side="left", fill="x", expand=True
    )
    ttk.Button(f_frame, text="Browse...", command=self.browse_audio).pack(
        side="right", padx=(5, 0)
    )

    ttk.Label(frame, text="Visualizer Resolution:").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    self.aud_res_var = tk.StringVar(value="720p")
    ttk.Combobox(
        frame,
        textvariable=self.aud_res_var,
        values=list(RESOLUTIONS.keys()),
        state="readonly",
    ).pack(fill="x", padx=10, pady=5)

    self.aud_status = ttk.Label(
        frame, text="Status: Ready", foreground="gray"
    )
    self.aud_status.pack(anchor="w", padx=10, pady=15)

    ttk.Button(
        frame, text="Convert to .xva", command=self.convert_audio
    ).pack(fill="x", padx=10, pady=10)

  def browse_audio(self):
    f = filedialog.askopenfilename(
        filetypes=[("Media Files", "*.mp3 *.wav *.mp4 *.mkv"), ("All Files", "*.*")]
    )
    if f:
      self.aud_path_var.set(f)

  def convert_audio(self):
    inp = self.aud_path_var.get()
    if not inp or not os.path.exists(inp):
      messagebox.showerror("Error", "Please select a valid audio/media file.")
      return

    out_file = filedialog.asksaveasfilename(
        defaultextension=".xva", filetypes=[("Xenon Audio (.xva)", "*.xva")]
    )
    if not out_file:
      return

    try:
      self.aud_status.config(
          text="Status: Converting Audio...", foreground="blue"
      )
      self.root.update_idletasks()

      w, h = RESOLUTIONS[self.aud_res_var.get()]

      with open(inp, "rb") as f:
        raw_audio = f.read()

      transformed = bytearray(b ^ XOR_KEY for b in raw_audio)
      header = MAGIC_XVA + struct.pack(">H", w) + struct.pack(">H", h)

      with open(out_file, "wb") as f_out:
        f_out.write(header + transformed)

      self.aud_status.config(text="Status: Success!", foreground="green")
      messagebox.showinfo("Success", "Successfully created .xva audio file!")
    except Exception as e:
      self.aud_status.config(text="Status: Failed", foreground="red")
      messagebox.showerror("Error", str(e))

  # ==================== 4. UNIVERSAL PLAYER TAB ====================
  def setup_player_ui(self):
    frame = ttk.LabelFrame(
        self.player_tab, text=" Universal Xenon Media Player & Viewer "
    )
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ttk.Label(frame, text="Select Xenon File (.xmv, .xv, .xmi, .axmi, .xmf, .xva):").pack(
        anchor="w", padx=10, pady=(10, 0)
    )
    f_frame = ttk.Frame(frame)
    f_frame.pack(fill="x", padx=10, pady=5)

    self.play_path_var = tk.StringVar()
    ttk.Entry(f_frame, textvariable=self.play_path_var, width=45).pack(
        side="left", fill="x", expand=True
    )
    ttk.Button(f_frame, text="Browse...", command=self.browse_playback).pack(
        side="right", padx=(5, 0)
    )

    self.play_status = ttk.Label(
        frame, text="Status: Ready", foreground="gray"
    )
    self.play_status.pack(anchor="w", padx=10, pady=15)

    ttk.Button(
        frame, text="Play / View Xenon File", command=self.play_file
    ).pack(fill="x", padx=10, pady=10)

    ttk.Label(
        frame,
        text="Note: Press 'q' in the media window to close playback.",
        foreground="gray",
        font=("Arial", 9, "italic"),
    ).pack(anchor="w", padx=10, pady=10)

  def browse_playback(self):
    f = filedialog.askopenfilename(
        filetypes=[
            (
                "All Xenon Files",
                "*.xmv *.xv *.xmi *.axmi *.xmf *.xva",
            ),
            ("All Files", "*.*"),
        ]
    )
    if f:
      self.play_path_var.set(f)

  def play_file(self):
    path = self.play_path_var.get()
    if not path or not os.path.exists(path):
      messagebox.showerror("Error", "Please select a valid Xenon file.")
      return

    try:
      self.play_status.config(
          text="Status: Validating magic bytes...", foreground="blue"
      )
      self.root.update_idletasks()

      with open(path, "rb") as f:
        data = f.read()

      if len(data) < 8:
        raise ValueError("File is too short or corrupted.")

      magic = data[0:4]
      width = struct.unpack(">H", data[4:6])[0]
      height = struct.unpack(">H", data[6:8])[0]

      if magic == MAGIC_XMV or magic == MAGIC_XV:
        fps_enc = struct.unpack(">I", data[8:12])[0]
        fps = fps_enc / 100.0
        payload = bytearray(b ^ XOR_KEY for b in data[12:])

        temp_p = "temp_play.avi"
        with open(temp_p, "wb") as f_out:
          f_out.write(payload)

        cap = cv2.VideoCapture(temp_p)
        win = f"Xenon Video Player ({width}x{height})"
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
        delay = int(1000 / fps) if fps > 0 else 30

        while cap.isOpened():
          ret, frame = cap.read()
          if not ret:
            break
          cv2.imshow(win, frame)
          if cv2.waitKey(delay) & 0xFF == ord("q"):
            break
        cap.release()
        cv2.destroyAllWindows()
        if os.path.exists(temp_p):
          os.remove(temp_p)

      elif magic == MAGIC_XMI:
        payload = bytearray(b ^ XOR_KEY for b in data[8:])
        img_np = np.asarray(payload, dtype=np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        win = f"Xenon Image Viewer (.xmi) - {width}x{height}"
        cv2.imshow(win, img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

      elif magic == MAGIC_AXMI:
        fps = float(data[8])
        payload = bytearray(b ^ XOR_KEY for b in data[9:])
        temp_ax = "temp_ax_play.avi"
        with open(temp_ax, "wb") as f_out:
          f_out.write(payload)

        cap = cv2.VideoCapture(temp_ax)
        win = f"Xenon Animated Player (.axmi) @ {int(fps)}fps"
        cv2.namedWindow(win, cv2.WINDOW_AUTOSIZE)
        delay = int(1000 / fps)

        while cap.isOpened():
          ret, frame = cap.read()
          if not ret:
            break
          cv2.imshow(win, frame)
          if cv2.waitKey(delay) & 0xFF == ord("q"):
            break
        cap.release()
        cv2.destroyAllWindows()
        if os.path.exists(temp_ax):
          os.remove(temp_ax)

      elif magic == MAGIC_XMF:
        dpi = struct.unpack(">H", data[8:10])[0]
        payload = bytearray(b ^ XOR_KEY for b in data[10:])
        img_np = np.asarray(payload, dtype=np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        win = f"Xenon Metadata Viewer (.xmf) | DPI: {dpi}"
        cv2.imshow(win, img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        messagebox.showinfo(
            "Xenon Metadata (.xmf)",
            f"Successfully loaded .xmf metadata!\nResolution: {width}x{height}\nDPI:"
            f" {dpi}",
        )

      elif magic == MAGIC_XVA:
        payload = bytearray(b ^ XOR_KEY for b in data[8:])
        # Audio Player UI feedback + visualizer screen simulation
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(
            canvas,
            "XENON AUDIO (.XVA PLAYING)",
            (50, height // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )
        win = f"Xenon Audio Visualizer ({width}x{height})"
        cv2.imshow(win, canvas)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
      else:
        raise ValueError(
            "Security Error: Invalid magic bytes or tampered file format!"
        )

      self.play_status.config(text="Status: Playback completed", foreground="gray")
    except Exception as e:
      self.play_status.config(text="Status: Error", foreground="red")
      messagebox.showerror("Playback Error", str(e))


if __name__ == "__main__":
  root = tk.Tk()
  app = XenonMediaApp(root)
  root.mainloop()