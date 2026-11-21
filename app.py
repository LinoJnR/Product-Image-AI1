import gc
import io
import zipfile
from pathlib import Path

import streamlit as st
from product_image_ai.ingest import MAX_ZIP_UNCOMPRESSED_BYTES, collect_uploaded_images, extract_zip_images, open_image_bytes
from product_image_ai.processing import make_white_background

st.set_page_config(page_title='Product Image AI', page_icon='🖼️', layout='wide')
st.title('🖼️ Product Image AI')
st.caption('Extract cleaner product images by removing backgrounds, detected hands/people, and soft shadows.')
st.info(
    'The app keeps visible product RGB pixels from the original image. Human removal and shadow cleanup are AI-mask operations. '
    'If a hand covers part of a product, the hidden detail cannot be recovered reliably; always inspect previews.'
)

with st.expander('Product extraction settings', expanded=True):
    remove_humans = st.checkbox('Remove detected hands, arms and people', value=True)
    zero_shadows = st.checkbox('Zero-shadow cleanup (remove low-confidence shadow pixels)', value=True)
    mask_threshold = st.slider('Edge and shadow cleanup strength', min_value=80, max_value=230, value=145, step=5,
                               help='Higher values remove more faint shadow pixels but can also trim soft product edges.')
    transparent_output = st.checkbox('Export transparent PNG instead of pure white JPG', value=False)
    st.caption('A pure white background is used when transparent PNG is not selected.')

left, right = st.columns(2)
with left:
    image_files = st.file_uploader('Upload multiple product images', type=None, accept_multiple_files=True, key='bulk_images')
with right:
    zip_file = st.file_uploader('Or upload a ZIP containing product images', type=['zip'], key='image_zip')
st.caption('Safety limits: 25 MB per image, 250 MB total uncompressed batch, and 500 files per ZIP.')

if st.button('Extract products', type='primary', use_container_width=True):
    uploaded, failures = collect_uploaded_images(image_files or [])
    if zip_file is not None:
        try:
            zip_images, zip_failures = extract_zip_images(zip_file)
            failures.extend(zip_failures)
            used = {name.casefold() for name, _ in uploaded}
            for name, data in zip_images:
                candidate = name
                stem, suffix = Path(name).stem, Path(name).suffix
                counter = 2
                while candidate.casefold() in used:
                    candidate = f'{stem}_{counter}{suffix}'
                    counter += 1
                used.add(candidate.casefold())
                uploaded.append((candidate, data))
        except Exception as exc:
            st.error(f'Could not read ZIP: {exc}')
            st.stop()

    combined_bytes = sum(len(data) for _, data in uploaded)
    if combined_bytes > MAX_ZIP_UNCOMPRESSED_BYTES:
        st.error('Combined uploads exceed the 250 MB batch limit. Reduce the batch size and try again.')
        st.stop()

    if not uploaded:
        st.warning('No valid images were found. Check the individual errors below.')
        st.session_state['processed_images'] = []
        st.session_state['processing_failures'] = failures
    else:
        st.write(f'**{len(uploaded):,} images ready for processing.**')
        progress = st.progress(0)
        status = st.empty()
        processed = []
        output_names = set()
        output_format = 'PNG' if transparent_output else 'JPEG'
        extension = 'png' if transparent_output else 'jpg'
        for index, (filename, image_data) in enumerate(uploaded, start=1):
            status.write(f'Processing {index:,} of {len(uploaded):,}: {filename}')
            try:
                image = open_image_bytes(image_data)
                original_size = image.size
                result = make_white_background(
                    image, remove_bg=True, transparent=transparent_output,
                    remove_humans=remove_humans, zero_shadows=zero_shadows,
                    mask_threshold=mask_threshold,
                )
                output = io.BytesIO()
                if output_format == 'PNG':
                    result.save(output, format='PNG', optimize=True)
                else:
                    result.save(output, format='JPEG', quality=95, optimize=True)
                stem = Path(filename).stem or f'image_{index}'
                output_name = f'{stem}.MAIN.{extension}'
                base = stem
                counter = 2
                while output_name.casefold() in output_names:
                    output_name = f'{base}_{counter}.MAIN.{extension}'
                    counter += 1
                output_names.add(output_name.casefold())
                processed.append((output_name, output.getvalue(), filename, original_size, result.size))
                del image, result, output
            except Exception as exc:
                failures.append((filename, str(exc)))
            finally:
                progress.progress(index / len(uploaded))
                gc.collect()
        status.empty()
        st.session_state['processed_images'] = processed
        st.session_state['processing_failures'] = failures
        st.session_state['processed_format'] = output_format

if 'processed_images' in st.session_state:
    processed = st.session_state['processed_images']
    failures = st.session_state.get('processing_failures', [])
    st.subheader('Processing results')
    good_col, bad_col = st.columns(2)
    good_col.metric('Products extracted', len(processed))
    bad_col.metric('Needs attention', len(failures))
    if processed:
        st.success('Processed images are ready to preview and export. Check that no product details were clipped.')
        cols = st.columns(4)
        for i, (output_name, data, source_name, original_size, final_size) in enumerate(processed[:8]):
            with cols[i % 4]:
                st.image(data, caption=output_name, use_container_width=True)
                st.caption(f'{original_size[0]} × {original_size[1]} px')
        if len(processed) > 8:
            st.caption(f'Showing 8 previews. All {len(processed)} images are included in the export.')
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
            for output_name, data, source_name, original_size, final_size in processed:
                zf.writestr(f'OUTPUT/IMAGES/MAIN/{output_name}', data)
        archive.seek(0)
        ext_label = 'PNG' if st.session_state.get('processed_format') == 'PNG' else 'JPG'
        st.download_button(f'Download clean product MAIN images ({ext_label})', data=archive.getvalue(),
                           file_name='Product_Image_AI_MAIN_Images.zip', mime='application/zip',
                           type='primary', use_container_width=True)
    if failures:
        with st.expander(f'Files that need attention ({len(failures)})'):
            for filename, error in failures:
                st.write(f'**{filename}** — {error}')

st.divider()
st.caption('Important: this version adds a human-segmentation pass and stronger mask thresholding to suppress soft shadows. It cannot guarantee perfect hand removal when hands overlap the product, reconstruct hidden product parts, or distinguish every unrelated object from the chosen product. Review each preview before publishing.')
