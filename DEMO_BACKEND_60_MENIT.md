# Persiapan demo Swapify — 60 menit

Panduan berdasarkan checkout `main`, Django lokal 5.2.17, diperiksa 4 November 2026. Nama app review di kode adalah **`review_rating`**, bukan `rating_review`. Fokus: backend `user_profile`, lalu review. Kode aplikasi tidak diubah. Pengujian kedua app: **126 tes lulus** pada SQLite lokal. Ini tidak membuktikan upload Cloudinary, layanan lokasi, atau konkurensi PostgreSQL di produksi berjalan saat demo.

## 1. Cara memakai satu jam ini

| Menit | Pelajari / kerjakan | Target |
|---|---|---|
| 0–8 | Bagian 2–4; buka file yang disebut | Bisa menjelaskan MVT dan data User–Profile |
| 8–23 | Bagian 5–7 sambil mengikuti kode | Bisa menelusuri register dan edit profil |
| 23–33 | Bagian 8–10 | Paham lokasi, onboarding, dan query profil |
| 33–40 | Bagian 11–12 | Paham review dan sintaks asing utama |
| 40–54 | Latihan A dan B; tambah C jika sempat | Bisa mengubah validasi dan query sendiri |
| 54–60 | Jawab soal bagian 15 tanpa membaca | Bisa menjelaskan keputusan kode |

Jika tertinggal: prioritaskan **edit profil → ModelForm → get_object → super → validasi → query review**. Mekanisme cache geocoding cukup pahami tujuannya. Jangan habiskan waktu membaca CSS atau kode Leaflet.

## 2. Naskah pembuka demo, sekitar 90 detik

“Saya menangani user_profile dan review_rating. Akun menggunakan User bawaan Django, sedangkan data tambahan seperti nama tampilan, bio, foto, preferensi, dan lokasi disimpan di Profile yang berelasi one-to-one dengan User.

Alurnya, request masuk melalui config/urls.py, kemudian diteruskan ke urls.py aplikasi dan view yang sesuai. Sebagian besar view saya menggunakan class-based view. Untuk edit profil, UpdateView mengambil profil pengguna yang sedang login melalui get_object, membuat ProfileUpdateForm dengan instance tersebut, lalu memvalidasi input saat POST. Kalau valid, foto baru diunggah jika ada, kemudian ModelForm menyimpan perubahan dan pengguna diarahkan kembali ke profil. Kalau invalid, form ditampilkan dengan pesan error.

Template bertugas menampilkan context dari view. Beberapa endpoint mendukung dialog melalui JavaScript, tetapi validasi dan pemeriksaan kepemilikan tetap dilakukan di backend. Untuk review, pengguna hanya bisa menilai partner pada transaksi yang selesai, satu kali per transaksi. Aturan itu diperiksa di service, dan batas rating serta keunikan juga diperkuat dengan constraint database.”

## 3. Peta MVT yang benar-benar dipakai

```text
Browser mengirim GET atau POST
  → middleware (session, identitas pengguna, CSRF untuk request terkait)
  → config/urls.py: prefix /profile/ atau /reviews/
  → urls.py app: pilih view melalui .as_view()
  → View: cek akses, ambil objek, pilih form / jalankan service
  → Form: validasi, normalisasi, cleaned_data
  → Model / ORM: baca atau simpan database
  → View membangun context
  → Template menjadi HTML, atau view menghasilkan JSON / redirect
  → Browser menampilkan hasil atau mengikuti redirect
```

Ini peta peran, bukan berarti setiap request selalu melewati seluruh langkah. GET detail tidak perlu form. POST lokasi resolve tidak merender template. Request yang gagal CSRF bisa berhenti sebelum view.

| Peran | File utama | Tanggung jawab |
|---|---|---|
| Model | `apps/user_profile/models.py` | Struktur Profile dan cache lokasi |
| View | `apps/user_profile/views.py` | Mengatur request, izin, query, form, respons |
| Template | `apps/user_profile/templates/user_profile/` | Menampilkan form, profil, error |
| Form | `apps/user_profile/forms.py` | Field yang boleh diisi dan validasinya |
| Service | `services.py`, `geocoding.py`, `common/images.py` | Upload dan operasi bisnis/eksternal |
| Signal | `apps/user_profile/signals.py` | Membuat Profile ketika User baru disimpan |
| URL | `config/urls.py` dan masing-masing `urls.py` | Memetakan alamat ke view |

Form, service, dan signal adalah pemisahan tanggung jawab di dalam aplikasi Django; bukan pengganti MVT. ORM mengubah operasi Python seperti `.filter()` menjadi query database.

### Alamat yang perlu kamu ingat

| URL | View | Kegunaan |
|---|---|---|
| `/profile/` | `MyProfileDetailView` | Profil pribadi, wajib login |
| `/profile/edit/` | `MyProfileUpdateView` | Edit nama, bio, foto |
| `/profile/register/` | `RegisterUserView` | Daftar, otomatis login, menuju onboarding |
| `/profile/login/` | `LoginUserView` | Login |
| `/profile/logout/` | `LogoutUserView` | Logout melalui POST |
| `/profile/onboarding/` | `OnboardingView` | Tiga langkah setup |
| `/profile/location/edit/` | `MyProfileLocationUpdateView` | Simpan lokasi |
| `/profile/location/resolve/` | `LocationResolveView` | POST koordinat untuk mencari wilayah |
| `/profile/preferences/edit/` | `MyProfilePreferencesUpdateView` | Edit preferensi |
| `/profile/reviews/?rating=5` | `MyReviewListView` | Review diterima, filter rating |
| `/profile/users/<username>/` | `PublicProfileDetailView` | Profil publik dan wardrobe |
| `/reviews/transaction/<uuid>/` | `ReviewCreateView` | Tulis review transaksi |

`app_name = "user_profile"` membuat namespace. `reverse("user_profile:edit")` menghasilkan URL dari nama route. Mengganti path tidak mengharuskan kita mengganti semua pemanggil. `.as_view()` mengubah class view menjadi callable yang bisa dipanggil URL resolver.

## 4. Model: User berbeda dari Profile

Buka `apps/user_profile/models.py:6`.

```python
user = models.OneToOneField(
    settings.AUTH_USER_MODEL,
    on_delete=models.CASCADE,
    related_name="profile",
)
```

- User mengurus identitas login: username, password hash, status aktif, dan field akun bawaan.
- Profile menyimpan data tambahan. `display_name` berbeda dari username; menggantinya tidak mengganti nama login.
- One-to-one memastikan satu User **maksimal** mempunyai satu Profile. Relasi itu sendiri tidak otomatis membuat Profile; signal yang membuatnya.
- `profile.user` menuju User; `user.profile` arah balik dari `related_name`.
- `profile.user_id` membaca nilai foreign key tanpa perlu mengambil objek User.
- `settings.AUTH_USER_MODEL` merujuk model akun yang dikonfigurasi. Proyek ini memakai User bawaan.
- `CASCADE`: jika User dihapus, Profile ikut dihapus.

Field yang lain:

| Field | Makna dan detail penting |
|---|---|
| `display_name` | CharField maksimal 225; wajib di form |
| `bio` | TextField boleh kosong; model belum membatasi 1.000 karakter |
| `preferences` | JSONField menyimpan list pilihan, misalnya `["tops", "shoes"]` |
| `onboarding_completed` | Penanda setup selesai, default False |
| `profile_picture` | CloudinaryField; referensi aset, bukan file gambar mentah di database |
| `latitude`, `longitude` | Koordinat boleh NULL; deteksi membulatkan ke dua desimal |
| `district`, `city`, `province` | Nama wilayah; model boleh kosong, form lokasi mewajibkan city dan province |

`blank=True` berhubungan dengan validasi form/model; `null=True` mengizinkan NULL di database. Keduanya berbeda. `default=list` memanggil pembuat list setiap objek baru; hindari `default=[]` karena objek mutable dapat dipakai bersama. `__str__` membuat objek terbaca sebagai nama tampilan di admin/shell, bukan mengubah data.

`GeocodingCacheEntry` bukan profil pengguna. Tabel ini menyimpan hasil lookup dan gerbang request bersama antar-worker. `key` adalah primary key; `expires_at` diindeks untuk pencarian berdasarkan waktu kedaluwarsa.

## 5. Kunci memahami CBV: kode yang tidak terlihat di views.py

Buka `apps/user_profile/views.py:222` dan `forms.py:141`.

```python
class MyProfileUpdateView(
    LoginRequiredMixin, ProfileDialogMixin, SuccessMessageMixin, UpdateView
):
    model = Profile
    form_class = ProfileUpdateForm

    def get_object(self, queryset=None):
        return self.request.user.profile
```

`UpdateView` sudah menyediakan pola GET form dan POST validasi/simpan. Karena itu tidak ada `if request.method == "POST"` di class ini. Dokumentasi Django menegaskan bahwa generic model form views menyimpan model melalui `form_valid()` bawaannya: [generic editing Django 5.2](https://docs.djangoproject.com/en/5.2/topics/class-based-views/generic-editing/).

### GET /profile/edit/

1. `LoginRequiredMixin` menolak akses anonim dengan redirect ke login.
2. `dispatch()` memilih penanganan GET.
3. `UpdateView` memanggil `get_object()`: profil user yang sedang login.
4. Form dibuat dengan `instance=profil_tersebut`, sehingga field berisi data lama.
5. Context berisi form dan objek profil. `get_template_names()` memilih halaman penuh atau partial dialog.
6. Template dirender menjadi HTML.

### POST /profile/edit/

1. Middleware memeriksa CSRF; mixin memeriksa login.
2. Ambil profil melalui `get_object()` yang sama.
3. Form menerima `request.POST`, `request.FILES`, dan `instance` profil.
4. `form.is_valid()` menjalankan konversi tipe dan validasi.
5. Invalid → `form_invalid()` menampilkan error, tidak menyimpan.
6. Valid → `MyProfileUpdateView.form_valid()` menangani foto jika ada.
7. `super().form_valid(form)` melanjutkan rantai mixin sampai `ModelFormMixin` menjalankan `form.save()` dan menghasilkan redirect.
8. Mode biasa mengembalikan HTTP 302. Mode dialog mengubah redirect menjadi JSON `{"redirect": "/profile/"}` dengan status 200.

Jadi `form_valid()` **bukan** method untuk memanggil `is_valid()` lagi. Ia dipanggil setelah form dinyatakan valid.

### Jika ditulis sebagai function-based view

Berikut padanan konseptual paling sederhana; tidak mencakup foto, dialog, atau messages:

```python
@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("user_profile:detail")
    else:
        form = ProfileUpdateForm(instance=profile)
    return render(request, "user_profile/profile_form.html", {"form": form})
```

Hafalkan padanan ini agar bisa menjelaskan apa yang dikerjakan class bawaan.

### Method mana diubah untuk tugas apa?

| Method / atribut | Gunakan ketika |
|---|---|
| `get_queryset()` | Mengatur kumpulan data: filter, urutan, select_related |
| `get_object()` | Menentukan satu objek yang ditampilkan/diedit |
| `get_context_data()` | Menambahkan data untuk template |
| `get_form_kwargs()` | Mengirim argumen tambahan ke constructor form |
| `form_valid()` | Menjalankan tindakan setelah validasi sukses |
| `form_invalid()` | Mengatur respons ketika validasi gagal |
| `get_success_url()` | Menentukan tujuan setelah berhasil |
| `get_template_names()` | Memilih template penuh atau partial |
| `render_to_response()` | Mengatur HTML/JSON serta header respons |
| `dispatch()` | Logika sebelum penanganan GET/POST di rantai view |
| `clean_<field>()` di form | Aturan validasi satu field |
| `clean()` di form | Aturan yang melibatkan beberapa field |

`DetailView` untuk satu objek; `ListView` untuk daftar dengan pagination; `CreateView` untuk membuat objek; `UpdateView` untuk mengubah objek; `FormView` memproses form tetapi tidak otomatis menyimpan model; `View` memberi kendali langsung atas `get/post`; `TemplateView` untuk tampilan berbasis template.

## 6. Form, penyimpanan, dan perlindungan kepemilikan

`ProfileUpdateForm.Meta.fields` berisi `display_name`, `bio`, `new_profile_picture`. Dua field pertama milik model; field ketiga dideklarasikan sendiri di form. Namanya sengaja berbeda dari `profile_picture` karena file perlu divalidasi dan diunggah dulu.

- `ModelForm` terhubung dengan model dan punya `.save()`.
- `forms.Form` memvalidasi input tanpa pemetaan penyimpanan model otomatis; contohnya `LocationCoordinatesForm`, `ProfilePhotoForm`, dan `ReviewForm`.
- `request.POST` berisi input biasa. File ada di `request.FILES`.
- `cleaned_data` berisi data hasil validasi/konversi. Jangan mengambil input mentah untuk melewati validasi.
- `instance=profile` berarti memperbarui objek itu. Tanpa instance, ModelForm biasanya akan membuat objek baru.
- `form.instance` adalah objek model di balik ModelForm; mengisinya belum sama dengan menyimpan database.
- `form.save(commit=False)` menghasilkan objek yang belum disimpan, sehingga bisa dimodifikasi dulu.
- `save(update_fields=[...])` hanya menulis kolom yang disebut. Jika menambahkan field pada form lokasi, perhatikan daftar ini.

Mengapa user tidak bisa mengedit profil orang lain dengan mengirim `user_id` palsu?

1. `get_object()` mengambil `request.user.profile`, bukan ID dari POST.
2. `Meta.fields` membatasi field yang diterima form; `user` tidak termasuk.
3. Harus login dan lolos CSRF untuk pengiriman form dari browser.

**Login saja tidak cukup untuk ownership.** CSRF juga bukan pemeriksaan kepemilikan. Header dialog pun bukan izin akses.

### Upload foto

`ImageField` di form memeriksa isi gambar. Validator bersama memeriksa ukuran dan format JPEG/PNG/WebP. Nilai maksimum byte di kode adalah `5 * 1024 * 1024`; batas tepatnya diterima karena penolakan memakai `>`.

```text
form valid → views.upload_profile_picture()
 → user_profile/services.py → common/images.py
 → Cloudinary → hasil resource
 → form.instance.profile_picture = hasil
 → super().form_valid(form) → form.save()
```

Tidak ada foto baru → foto lama tetap. Upload gagal → `form.add_error("new_profile_picture", ...)` lalu `form_invalid()`; nama/bio juga tidak disimpan. Form HTML memakai `enctype="multipart/form-data"` agar file terkirim. Atribut `accept` di HTML hanya membantu pemilih file; validasi backend tetap diperlukan.

`transaction.atomic()` hanya mencakup transaksi database, tidak otomatis membatalkan upload Cloudinary. Jangan mengklaim file di layanan eksternal ikut rollback.

## 7. Registrasi, signal, login, logout

Buka `views.py:52`, `forms.py:97`, `signals.py:7`, `apps.py:8`.

```text
POST register
 → RegisterForm (turunan UserCreationForm)
 → validasi username, password, konfirmasi, name, agreement
 → RegisterUserView.form_valid() dalam transaksi database
 → super().form_valid(form) menyimpan User
 → post_save User menjalankan create_user_profile()
 → Profile dibuat dengan display_name awal = username
 → self.object sekarang adalah User baru
 → ubah self.object.profile.display_name menjadi form.cleaned_data["name"]
 → login(request, User baru)
 → kembalikan respons redirect ke onboarding
```

Meskipun variabel `response` sudah dibuat lebih awal, respons belum dikirim ke browser; method masih melanjutkan perubahan profil dan login sebelum `return response`.

`UserCreationForm` mengurus validasi password dan penyimpanan hash. Jangan mengganti dengan `user.password = request.POST["password"]`; password harus diproses melalui mekanisme hashing Django.

`name` dan `community_agreement` adalah field tambahan form. `name` dipakai untuk Profile. Checkbox agreement wajib dicentang supaya valid, tetapi tidak disimpan sebagai riwayat persetujuan di model saat ini.

Signal terdaftar karena `UserProfileConfig.ready()` mengimpor `signals`. `@receiver(post_save, sender=...)` mendengarkan penyimpanan User:

- `created=True`: baru dibuat; buat Profile.
- `raw=True`: pemuatan fixture; dilewati.
- `get_or_create()` mencegah pembuatan ganda dalam pola ini, diperkuat relasi one-to-one.
- `dispatch_uid` mencegah receiver yang sama terdaftar berulang.
- `using` menjaga operasi menggunakan alias database yang sama.

Signal tidak berjalan ketika profil sekadar dibaca. User lama yang kehilangan profil ditangani migration backfill `0002`, bukan diperbaiki otomatis oleh setiap `get_object()`.

`LoginUserView` mewarisi `LoginView`; `LoginForm` mewarisi `AuthenticationForm`. Logika autentikasi bawaan tetap dipakai, sementara kode lokal banyak mengatur widget. Login menyimpan identitas autentikasi di session; browser membawa cookie session pada request berikutnya, dan AuthenticationMiddleware menyediakan `request.user`. Bukan mengirim ulang password setiap membuka halaman.

`LOGIN_URL` dan `LOGIN_REDIRECT_URL` ada di `config/settings.py:198`. Tujuan `next` dapat mengembalikan pengguna ke halaman asal jika aman. Pengguna yang sudah login diarahkan keluar dari halaman login/register. Logout di Django yang dipakai proyek ini menggunakan POST, lalu menuju home.

## 8. Profil pribadi, publik, review, dan wardrobe

### Profil pribadi: `views.py:137`

`get_object()` mengambil profil sendiri. Review dibatasi `recipient=self.request.user`, yaitu review **yang diterima**, bukan yang ditulis. `.aggregate(average=Avg("rating"), count=Count("pk"))` menghasilkan satu dictionary statistik. Jika kosong: average `None`, count `0`; jangan membuat rating palsu 0/5. `.first()` mengambil review terbaru karena `Review.Meta.ordering` adalah `-created_at`, lalu `-pk`.

`.select_related("author__profile")` mengambil relasi author dan profilnya lewat SQL JOIN untuk menghindari query tambahan per kartu review. Ini optimasi pengambilan data, bukan filter izin.

### Daftar review pribadi: `views.py:158`

`get_queryset()` menyimpan semua review diterima dalam `self.received_reviews`, memvalidasi `?rating=` dengan whitelist 1–5, kemudian mengembalikan daftar terfilter. `paginate_by = 10` membuat ListView menangani `?page=2`.

Statistik dihitung dari `self.received_reviews`, sehingga tetap mewakili semua review walaupun daftar difilter rating 5. Jika ingin statistik ikut filter, gunakan queryset terfilter sebelum pagination. Tentukan perilaku yang diminta penguji sebelum mengubahnya.

### Profil publik: `views.py:314`

- Bisa dilihat tanpa login; queryset hanya akun `user__is_active=True`.
- `get_object_or_404(..., user__username=self.kwargs["username"])` mencari pemilik profil dari URL.
- `user__username` adalah lookup ORM menyeberangi relasi; `self.kwargs` di sini berasal dari parameter URL.
- `is_owner` membandingkan ID pengunjung dan pemilik profil.
- `member_listings()` di `apps/clothing_catalog/selectors.py` membatasi owner dan status AVAILABLE, lalu memakai filter katalog bersama.
- Wardrobe 12 barang per halaman (`wardrobe_page`); review 10 per halaman (`reviews_page`). Nama parameter terpisah agar tidak bertabrakan.
- Owner mendapat anotasi ID swap request pending terbaru untuk tiap barang; pengunjung lain tidak mendapat anotasi tersebut.
- Template publik tidak menampilkan koordinat atau detail transaksi privat; keberadaan field di model tidak otomatis membuatnya tampil di HTML.

`OuterRef("pk")` berarti PK barang pada query luar. `Subquery(...values("pk")[:1])` mengambil satu ID request pending terbaru untuk barang itu. `annotate()` menambahkan hasil per objek query, **bukan kolom permanen**. Cukup pahami ini; jangan memulai belajar query lanjutan dari bagian ini.

## 9. Lokasi: dua request, belum disimpan saat detect

Buka `views.py:284` dan `forms.py:16`.

```text
1. Browser meminta geolocation dengan izin pengguna.
2. JavaScript mengirim POST koordinat ke location/resolve/.
3. LocationCoordinatesForm memvalidasi rentang latitude dan longitude.
4. reverse_geocode() membulatkan ke 2 desimal dan mencari nama wilayah.
5. Backend membuat token berisi wilayah, koordinat, user_id.
6. JSON mengirim district/city/province dan token ke browser.
7. Pengguna menekan simpan → POST location/edit/.
8. ProfileLocationForm.clean() memverifikasi token dan kecocokan data.
9. Form.save() menyimpan wilayah dan koordinat yang sesuai.
```

Token memakai `signing.dumps/loads`, salt `user_profile.location`, dan usia maksimum 1.800 detik (30 menit). Signing mendeteksi perubahan data; **bukan enkripsi**. Token yang ditandatangani dapat dibaca isinya. Salt memisahkan konteks pemakaian token.

- Token rusak/kedaluwarsa → error validasi.
- Token pengguna lain → error.
- Nama wilayah sama persis dengan isi token → koordinat token diterapkan.
- Pengguna mengedit nama wilayah → lokasi diperlakukan manual; jika field wilayah berubah, koordinat lama dihapus agar tidak menunjuk wilayah yang berbeda.
- Wilayah manual tidak berubah dan tidak ada token → koordinat lama dipertahankan.
- POST mentah latitude/longitude ke form edit tidak langsung disimpan; field tersebut bukan field ModelForm lokasi.

**Batas jaminan:** signing mengikat hasil lookup ke user dan mendeteksi modifikasi sesudah server menerbitkan token. Klien masih bisa mengirim koordinat pilihan sendiri ke endpoint resolve. Fitur ini bukan bukti bahwa pengguna secara fisik berada di lokasi itu.

`reverse_geocode()` di `geocoding.py:59`:

1. Bulatkan koordinat dan cek cache database yang belum kedaluwarsa.
2. Jika tidak ada cache, coba mengambil gerbang request bersama melalui conditional `.update()`.
3. Jika gerbang sedang dipakai, keluarkan `GeocodingBusy` → HTTP 429.
4. Hubungi Nominatim dengan timeout 5 detik dan User-Agent aplikasi.
5. Petakan respons menjadi district/city/province, termasuk kasus Jakarta.
6. Simpan hasil satu hari; akhirnya lepaskan gerbang dengan cooldown.

Gate awal 30 detik; cooldown normal 1,1 detik. Respons 429 dari penyedia memberi cooldown 60 detik tetapi dipetakan menjadi GeocodingError/503 ke klien. HTTP 429 lokal berasal dari gerbang sibuk. SHA-256 di cache key mengidentifikasi endpoint; bukan hashing password.

`LocationResolveView` memberi `Cache-Control: no-store` untuk respons lookup yang telah diproses service; jalur koordinat invalid langsung mengembalikan 400 lebih awal. Jangan mengklaim semua cabang respons memakai header yang sama.

`safe_return_url()` memeriksa tujuan `next` agar redirect setelah edit lokasi tidak mengarah ke host sembarangan.

## 10. Onboarding: simpan bertahap

Buka `views.py:408`.

`OnboardingView` memakai `View`, sehingga `get()` dan `post()` ditulis eksplisit. GET mengambil langkah, membatasi tampilan 1–4, dan membangun tiga form. POST memilih satu form sesuai step:

1. `OnboardingProfileForm`: nama, bio, foto; bio maksimal 1.000.
2. `OnboardingLocationForm`: lokasi serta checkbox persetujuan wajib.
3. `PreferencesForm`: list pilihan style, boleh kosong; berhasil menyetel `onboarding_completed=True`.

Setiap langkah disimpan sendiri. “Later” menuju katalog dan mempertahankan langkah yang sudah tersimpan. Step diambil dari POST dan harus 1, 2, atau 3. Saat ini backend **tidak mewajibkan** step 1 dan 2 selesai sebelum menerima POST step 3; flag selesai bukan bukti semua data wajib sudah lengkap. Jangan menjelaskan wizard ini seolah memiliki pemeriksaan urutan ketat.

Cabang `action=upload_photo` menyimpan foto langsung tanpa menyimpan nama/bio dari request itu. `action=later` tidak menyelesaikan onboarding. `X-Requested-With: XMLHttpRequest` memilih respons JSON sukses/error; request biasa mendapat redirect atau HTML.

## 11. Review: izin dan aturan bisnis

Buka `apps/review_rating/views.py:18`, `services.py:9`, `models.py:12`.

```text
GET/POST /reviews/transaction/<uuid>/
 → LoginRequiredMixin
 → exchange: cari transaksi hanya di antara transaksi partisipan
 → bukan partisipan / tidak ada: 404
 → belum COMPLETED: 403 dari PermissionDenied
 → ReviewForm memvalidasi rating dan comment
 → submit_review(..., author=request.user)
 → cek ulang aturan, buat Review, full_clean(), save()
 → redirect detail transaksi, atau JSON konfirmasi untuk dialog
```

`exchange` memakai `@cached_property`: pada instance view/request yang sama, hasilnya dihitung sekali lalu dipakai lagi. Bukan cache permanen antar-user. `get_form_kwargs()` sengaja mengakses `self.exchange` supaya izin transaksi diperiksa juga sebelum pemrosesan form yang invalid.

`Q(requester=user) | Q(owner=user)` berarti salah satu pihak. `ReviewForm.rating` memakai `TypedChoiceField(coerce=int)`: string POST `"5"` menjadi integer `5`. Komentar opsional maksimal 1.000 karakter.

### Apa yang dilakukan `submit_review()`?

1. `@transaction.atomic`: operasi database dalam satu transaksi.
2. Tolak author anonim.
3. `select_for_update().get()` mengambil serta mengunci baris transaksi di database yang mendukungnya.
4. Pastikan author partisipan dan transaksi COMPLETED.
5. `.exists()` memeriksa apakah author sudah menulis review pada transaksi itu.
6. Tentukan recipient di server: partner author, bukan dari input browser.
7. Buat objek Review, rapikan comment dengan `.strip()`.
8. `full_clean()` menjalankan validasi model, kemudian `.save()` menulis database.

Mengapa validasi view dan service berulang? View memberi respons HTTP dan konteks halaman; service menjaga aturan bisnis apabila kelak dipanggil dari tempat lain, sekaligus membaca ulang status saat penyimpanan.

### Perlindungan model/database

| Aturan | Implementasi |
|---|---|
| Satu review per author per transaksi | UniqueConstraint(transaction, author) |
| Rating 1–5 | Validator dan CheckConstraint |
| Author bukan recipient | CheckConstraint menggunakan Q dan F |
| Transaksi yang direferensikan review tidak dihapus | FK `on_delete=PROTECT` |
| Akun author/recipient dihapus | FK `on_delete=CASCADE` menghapus review terkait |
| Tampilan terbaru dahulu | ordering `-created_at`, `-pk` |

`F("recipient")` merujuk nilai kolom recipient pada baris tersebut; bukan string input. `~Q(...)` adalah NOT. Dua pengguna boleh sama-sama mereview transaksi yang sama, masing-masing sekali.

Model tidak punya constraint database untuk “author benar-benar partisipan dan transaksi selesai”; itu diperiksa di service/view. `save()` biasa tidak otomatis menjalankan `full_clean()`, sehingga pemanggilan eksplisit di service penting. Lihat [validasi model Django](https://docs.djangoproject.com/en/5.2/ref/models/instances/#validating-objects).

`select_for_update` membantu mencegah dua request bersamaan melewati cek duplikat dengan mengunci transaksi yang sama. **SQLite tidak menerapkan row lock ini**; PostgreSQL mendukungnya. UniqueConstraint tetap menjadi pengaman keunikan. Pengujian lokal biasa bukan pembuktian perilaku race di produksi. Rujukan: [QuerySet select_for_update](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).

## 12. Kode yang mungkin terasa asing

Saya belum melihat tutorial kelasmu, jadi daftar ini adalah kandidat konsep lanjutan, bukan klaim bahwa konsep tersebut tidak pernah diajarkan.

| Bentuk kode | Arti praktis di proyek |
|---|---|
| `self` | Instance objek saat ini; pada view, menyimpan request dan objek yang diproses |
| `self.request` | Request yang sedang ditangani instance class view |
| `self.object` | Objek utama CBV: Profile di UpdateView; User setelah register disimpan |
| `*args`, `**kwargs` | Menerima argumen posisi dan keyword tambahan; menjaga kompatibilitas method induk |
| `super()` | Lanjut ke implementasi berikutnya menurut urutan pewarisan Python/MRO |
| `class Meta` | Konfigurasi Model/ModelForm: fields, constraints, ordering, widget |
| `__init__` | Menyesuaikan instance form; `super().__init__` membuat field bawaan lebih dulu |
| `{**dictionary, "key": value}` | Membuat dictionary gabungan; key terakhir menggantikan key yang sama |
| `[*fields, "latitude"]` | Mengembangkan isi iterable ke list baru |
| `image := expression` | Walrus operator: simpan hasil ke image sekaligus pakai dalam kondisi |
| `@property` | Method dibaca seperti atribut; misalnya `exchange.owner` |
| `@cached_property` | Seperti property, tetapi hasil disimpan pada instance setelah akses pertama |
| `@transaction.atomic` | Decorator yang membungkus pemanggilan dalam transaksi database |
| `with transaction.atomic():` | Versi blok: transaksi hanya untuk bagian di dalam blok |
| `except ... as error` | Tangkap kegagalan yang diantisipasi dan beri respons yang sesuai |
| `raise ... from error/None` | Mengatur hubungan traceback exception; tidak mengubah aturan validasi |
| `.filter()` / `.get()` | Kumpulan hasil / tepat satu objek; get bisa melempar DoesNotExist |
| `.get_or_create()` | Ambil objek jika ada, buat jika belum; return `(object, created)` |
| `__gte`, `__lte`, `__icontains` | Lookup ORM: ≥, ≤, pencarian teks tanpa peka huruf besar/kecil |
| `aggregate()` | Menghasilkan ringkasan untuk seluruh kumpulan, misalnya average/count |
| `annotate()` | Menambahkan hasil per baris objek, misalnya pending_request_id |
| `select_related()` | JOIN untuk mengambil relasi FK/one-to-one bersama query utama |
| `OuterRef`, `Subquery` | Query di dalam query yang dapat merujuk baris query luar |
| `reverse_lazy()` | Menunda pencarian URL; cocok sebagai atribut class saat modul diimpor |
| `form.add_error(None, ...)` | Error umum/non-field, contohnya review duplikat |

### Mixin dan `super()` pada edit profil

Urutan lokal yang sudah diperiksa dimulai dengan:

```text
MyProfileUpdateView → LoginRequiredMixin → AccessMixin
 → ProfileDialogMixin → SuccessMessageMixin → UpdateView → ...
```

Tidak semua class mengimplementasikan setiap method. Python mencari implementasi berikutnya yang ada. Untuk `form_valid`, method milik view melakukan upload, kemudian ProfileDialogMixin memanggil lanjutan, SuccessMessageMixin meneruskan ke penyimpanan model dan menambah pesan, lalu ProfileDialogMixin dapat mengubah redirect menjadi JSON.

Jadi jangan mengartikan `super()` sebagai “panggil langsung UpdateView” dalam semua situasi. Mixin memungkinkan perilaku login, pesan sukses, dan dialog dipakai bersama tanpa ditulis ulang pada setiap view.

### JSON, partial, dan status HTTP

`ProfileDialogMixin` membaca `X-Profile-Dialog: 1`: GET mengirim partial HTML; POST sukses mengirim JSON redirect; form invalid mengirim HTML error dengan 422. Header `X-Profile-Reviews` dan `X-Member-Wardrobe` menghasilkan JSON berisi HTML hasil `render_to_string`. JSON tidak selalu berisi data mentah.

`patch_vary_headers()` memberi tahu cache bahwa respons bisa berbeda berdasarkan header tertentu; bukan mekanisme izin. Halaman penuh dan dialog memakai backend validasi yang sama.

| Status | Contoh lokal |
|---|---|
| 200 | HTML/JSON berhasil; form invalid halaman biasa juga bisa 200 |
| 302 | Redirect setelah simpan/login atau menuju login |
| 400 | Koordinat/step onboarding tidak valid |
| 403 | CSRF gagal, atau review transaksi belum selesai |
| 404 | Username tidak ada atau transaksi tidak ditemukan dalam scope partisipan |
| 405 | Method HTTP tidak didukung, misalnya GET ke resolve/logout |
| 422 | Error form dialog, atau hasil wilayah tidak lengkap dari geocoding |
| 429 | Gerbang lookup lokasi sedang sibuk |
| 503 | Layanan lookup tidak tersedia |

## 13. Latihan live coding — kerjakan dulu, baru lihat jawaban

Contoh berikut adalah **usulan latihan**, belum diterapkan ke aplikasi. Pilih A dan B dahulu. Saat demo: ulangi kebutuhan, pilih lapisan yang tepat, ubah sedikit, lalu cek satu input valid dan satu invalid. Jangan mengubah semua file sekaligus.

### A. Batasi bio menjadi 300 karakter pada edit dan onboarding (5 menit)

Tentukan apakah batas berlaku pada semua jalur backend atau hanya form. Untuk latihan ini, targetnya kedua form. `maxlength` HTML saja tidak cukup. Ingat onboarding mendefinisikan field bio sendiri sehingga override field parent tidak otomatis mengganti batas field child.

Jawaban minimal: tambahkan method di `ProfileUpdateForm`. Karena `OnboardingProfileForm` mewarisinya dan tidak menimpa method ini, keduanya memakai validasi yang sama:

```python
def clean_bio(self):
    bio = self.cleaned_data.get("bio", "")
    if len(bio) > 300:
        raise forms.ValidationError("Bio maksimal 300 karakter.")
    return bio
```

Tidak perlu migration karena struktur model tidak diubah. Sesuaikan juga label bantuan/maxlength/counter onboarding yang sebelumnya menyebut 1.000 agar UI konsisten. Method ini tidak melindungi penulisan langsung melalui ORM; jika diminta aturan lintas semua pemanggil, pertimbangkan validator model serta cara pemanggilan validasinya.

Cek cepat tanpa menyimpan database:

```bash
env/bin/python manage.py shell
```

```python
from apps.user_profile.forms import ProfileUpdateForm, OnboardingProfileForm

for Form in (ProfileUpdateForm, OnboardingProfileForm):
    for size in (300, 301):
        form = Form({"display_name": "Alfi", "bio": "a" * size})
        print(Form.__name__, size, form.is_valid(), form.errors.as_text())
```

Hasil yang diharapkan setelah perubahan: 300 valid, 301 invalid pada kedua form. Tes lama yang mengharapkan pesan/batas lama mungkin perlu disesuaikan jika requirement resmi berubah.

### B. Tambahkan filter pencarian komentar di review pribadi (5 menit)

Target: `/profile/reviews/?q=ramah`, tetap dibatasi review yang diterima user login, pagination tetap bekerja, statistik tetap keseluruhan.

Di `MyReviewListView.get_queryset()`, pertahankan pembuatan `self.received_reviews` dan whitelist `self.rating`; ganti bagian return akhir menjadi:

```python
queryset = self.received_reviews
if self.rating:
    queryset = queryset.filter(rating=self.rating)
self.search = self.request.GET.get("q", "").strip()
if self.search:
    queryset = queryset.filter(comment__icontains=self.search)
return queryset
```

Lalu di `get_context_data()` tambahkan `context["search"] = self.search` sebelum return. Itu menyediakan nilai input pencarian di template. Untuk UI lengkap, tambahkan input bernama `q` dan pertahankan parameter `q` di tautan pagination/filter; backend bisa diperiksa langsung melalui URL dahulu.

Cek: komentar cocok muncul, komentar tak cocok hilang, review penerima lain tetap tak terlihat, `rating=5&q=ramah` menggabungkan kedua filter. Jangan mulai dari `Review.objects.all()` karena scope pengguna akan hilang.

### C. Tambahkan jumlah review bintang lima (2 menit)

Target pertama hanya profil pribadi. Pada `MyProfileDetailView.get_context_data()`, setelah queryset `reviews` tersedia:

```python
context["five_star_count"] = reviews.filter(rating=5).count()
```

Template dapat menampilkan `{{ five_star_count }}`. Tidak perlu migration, karena nilai dihitung dari data yang sudah ada. Jika diminta di profil publik juga, tambah context di PublicProfileDetailView memakai `received_reviews` milik target, bukan request.user.

### D. Tambahkan field Instagram pada profil (opsional 6 menit)

1. Tambahkan di model Profile:

```python
instagram = models.CharField(max_length=30, blank=True)
```

2. Tambahkan `"instagram"` pada `ProfileUpdateForm.Meta.fields`.
3. Tambahkan field di partial edit profil karena template ini merender field satu per satu:

```django
{% include "user_profile/auth/field.html" with field=form.instagram %}
```

4. Jalankan migration saat perubahan itu memang dikerjakan:

```bash
env/bin/python manage.py makemigrations user_profile
env/bin/python manage.py migrate
```

5. Tampilkan `profile.instagram` di halaman yang diminta; uji simpan dan buka ulang.

`OnboardingProfileForm` mewarisi form ini sehingga field baru juga masuk ke form onboarding. Putuskan apakah perlu ditampilkan di onboarding atau `Meta.fields` child perlu dibatasi. Jangan terkejut karena efek inheritance.

`blank=True` membuat field opsional dan memudahkan penambahan ke data lama. Gunakan `URLField` jika requirement meminta URL lengkap, bukan handle. Jangan mengedit migration lama yang sudah diterapkan.

### E. Rating rendah wajib punya komentar (opsional 4 menit)

Ini aturan melibatkan rating dan comment, sehingga cocok di `ReviewForm.clean()`. Untuk menjamin aturan juga saat service dipanggil tanpa form, tambahkan pemeriksaan di `submit_review()` sesudah comment dinormalisasi dan sebelum penyimpanan.

Contoh form:

```python
def clean(self):
    cleaned = super().clean()
    rating = cleaned.get("rating")
    comment = cleaned.get("comment", "").strip()
    if rating is not None and rating <= 2 and not comment:
        self.add_error("comment", "Jelaskan alasan rating rendah.")
    return cleaned
```

Contoh logika service setelah cek izin/status/duplikat:

```python
comment = comment.strip()
if rating <= 2 and not comment:
    raise ValidationError("Jelaskan alasan rating rendah.")
```

Contoh service ini mengasumsikan rating sudah berupa integer valid seperti pemanggil form saat ini. Jika service juga harus menerima input mentah lain, normalisasikan/validasi tipe dahulu agar tidak muncul TypeError. Cek rating 1 tanpa komentar ditolak, rating 1 berkomentar diterima, rating 5 tanpa komentar diterima.

## 14. Cara memilih file saat diberi soal mendadak

| Permintaan | Mulai dari |
|---|---|
| Tambah informasi yang harus disimpan | Model → migration → form → template/view terkait |
| Ubah batas/aturan input | Form; model/service jika berlaku lebih luas |
| Tambah filter/urutan data | `get_queryset()` atau query di `get_context_data()` |
| Tambah statistik | `aggregate/count` lalu context |
| Cegah edit milik orang lain | Login + `get_object()`/queryset dengan ownership |
| Buat endpoint baru | URL → view → izin → form/service → respons |
| Ubah tujuan setelah sukses | `success_url` / `get_success_url()` |
| Review boleh diubah/dihapus | Objek harus difilter `author=request.user`; putuskan aturan status transaksi |
| Foto gagal upload | Form errors, wrapper service, konfigurasi penyedia; jangan lewatkan validasi |

Urutan debug: **URL benar → user/izin benar → form errors → cleaned_data → objek/field yang disimpan → respons → tampilan**. `print(form.errors)` lebih berguna daripada menebak mengapa penyimpanan tidak terjadi. Jangan mencetak password, token rahasia, atau kredensial layanan.

Perintah verifikasi yang sudah dipakai pada checkout awal:

```bash
PRODUCTION=False env/bin/python manage.py test apps.user_profile apps.review_rating --noinput
```

Jalankan tes terarah saat perubahan kecil, misalnya:

```bash
PRODUCTION=False env/bin/python manage.py test apps.user_profile.tests.ProfileEditingTests
```

TestCase memakai database pengujian; `force_login()` hanya bantuan tes. `refresh_from_db()` mengambil data yang benar-benar tersimpan. `patch()` mengganti pemanggilan Cloudinary/geocoding agar tes tidak bergantung internet. Karena itu “tes upload lulus” bukan bukti kredensial Cloudinary saat demo valid.

## 15. Simulasi tanya-jawab terakhir

Tutup jawabannya dan ucapkan jawabanmu sendiri dahulu.

1. **Di mana profil disimpan saat tidak ada `.save()` di view edit?** Pada form_valid bawaan ModelFormMixin yang dicapai melalui `super()`, lalu `form.save()`.
2. **Kenapa user tidak bisa mengedit profil orang lain?** Objek diambil dari request.user.profile dan form membatasi field, bukan mengandalkan ID dari browser.
3. **Apa beda username dan display_name?** Username identitas login pada User; display_name nama tampilan pada Profile.
4. **Apa yang menciptakan Profile?** Signal post_save User yang diimpor melalui AppConfig.ready, bukan OneToOneField sendiri.
5. **Apa bedanya GET dan POST edit?** GET menyiapkan form dari instance; POST mengikat data, memvalidasi, lalu menyimpan bila valid.
6. **Apa peran cleaned_data?** Data yang lolos proses validasi dan konversi form.
7. **Kapan perlu migration?** Saat struktur/state model berubah; ubah validasi form atau filter view saja tidak perlu.
8. **Mengapa tidak menyimpan koordinat langsung dari POST edit?** Form edit hanya menerima wilayah dan token; server memeriksa data lokasi yang telah ditandatangani.
9. **Apakah token lokasi terenkripsi atau membuktikan GPS asli?** Tidak. Ia mendeteksi perubahan setelah penerbitan, terikat user dan usia; input lokasi awal berasal dari klien.
10. **Apa yang dilakukan select_related?** Mengambil relasi lewat JOIN untuk menghindari query tambahan per item, bukan memberikan izin.
11. **Apa beda aggregate dan annotate?** Satu ringkasan kumpulan versus nilai tambahan per baris hasil.
12. **Kenapa ReviewForm bukan ModelForm?** Identitas author, recipient, dan transaksi diputuskan server; service secara eksplisit memvalidasi dan menyimpan review.
13. **Bagaimana mencegah dua review dari user yang sama?** Cek duplikat di service, transaksi/lock pada database pendukung, dan UniqueConstraint.
14. **Apakah satu transaksi hanya boleh punya satu review total?** Tidak. Masing-masing partisipan boleh satu, jadi normalnya dua.
15. **Apakah `.save()` otomatis memvalidasi semua model?** Tidak; service review memanggil full_clean secara eksplisit.
16. **Apa beda 403 dan 404 pada review?** Transaksi di luar scope partisipan tidak ditemukan → 404; transaksi milik partisipan tetapi belum selesai → 403 di view.
17. **Mengapa perlu super pada get_context_data?** Mempertahankan context bawaan seperti form/object/pagination, kemudian menambahkan data sendiri.
18. **Apakah header dialog dapat melewati login?** Tidak. Header hanya memilih bentuk respons.
19. **Bagaimana bio dibatasi sekarang?** Onboarding maksimal 1.000; edit biasa/model bio belum punya batas yang sama.
20. **Apakah onboarding menjamin urutan 1–2–3?** Belum; tiap step bisa disimpan terpisah, dan POST step 3 menandai selesai.

Kalau belum bisa menjawab 1, 2, 4, 5, 6, dan 7 tanpa melihat, ulangi bagian 5–7 sebelum membaca mekanisme lokasi yang lebih rumit.
