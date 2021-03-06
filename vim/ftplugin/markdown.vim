" Language: Markdown
" Maintainer: Swaroop C H <swaroop@swaroopch.com>
" URL: https://github.com/swaroopch/vim-markdown-preview
" License: WTFPL
" Dependencies: http://fletcherpenney.net/multimarkdown/

if exists("b:loaded_markdown_preview")
    finish
endif

let b:loaded_markdown_preview = 1

function! s:open_file(filename)
    if has('mac') || has('macunix')
        call system("open " . fnameescape(a:filename))
    elseif has('unix')
        call system("gnome-open " . fnameescape(a:filename))
    elseif has('windows')
        call system(fnameescape(a:filename))
    endif
endfunction

function! s:ShowMarkdownPreview(line1, line2)
    let text = getline(a:line1, a:line2)
    if has('windows')
        let output_text_filename = $HOME . '/markdown-preview.md'
        let output_html_filename = $HOME . '/markdown-preview.html'
    else
        let output_text_filename = "/tmp/markdown-preview.md"
        let output_html_filename = "/tmp/markdown-preview.html"
    endif
    call writefile(text, output_text_filename)
    call writefile(["<!doctype html><html><head><meta charset='UTF-8'></head><body>"], output_html_filename)
    if has('windows') 
        exec 'silent !multimarkdown ' . output_text_filename . ' >> ' . output_html_filename
    else
        call system('multimarkdown ' . output_text_filename . ' >> ' . output_html_filename)
    endif
    call s:open_file(output_html_filename)
endfunction

command! -range=% MarkdownPreview call s:ShowMarkdownPreview(<line1>, <line2>)
