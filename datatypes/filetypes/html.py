# -*- coding: utf-8 -*-
from collections.abc import Iterable
from collections import Counter
from functools import cached_property
import re

from ..compat import *
from ..string import String
from ..token import Scanner


class HTML(String):
    """Adds HTML specific methods on top of the String class"""

    # https://developer.mozilla.org/en-US/docs/Glossary/Void_element
    # https://developer.mozilla.org/en-US/docs/Glossary/Empty_element
    # void, or empty, elements are elements that don't have a body
    VOID_TAGNAMES = set([
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "keygen",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ])

    # https://developer.mozilla.org/en-US/docs/Web/HTML/Block-level_elements
    # https://www.w3schools.com/html/html_blocks.asp
    BLOCK_TAGNAMES = set([
        "article",
        "aside",
        "blockquote",
        "body",
        "br",
        "button",
        "canvas",
        "caption",
        "col",
        "colgroup",
        "dd",
        "div",
        "dl",
        "dt",
        "embed",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "hr",
        "li",
        "map",
        "object",
        "ol",
        "output",
        "p",
        "pre",
        "progress",
        "section",
        "table",
        "tbody",
        "textarea",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
        "video",
    ])

    # https://www.w3schools.com/html/html_blocks.asp
    # NOTE: an inline element cannot contain a block-level element
    INLINE_TAGNAMES = set([
        "a",
        "abbr",
        "acronym",
        "b",
        "bdo",
        "big",
        "cite",
        "code",
        "dfn",
        "em",
        "i",
        "img",
        "input",
        "kbd",
        "label",
        "map",
        "object",
        "output",
        "q",
        "samp",
        "script",
        "select",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "tt",
        "var",
    ])

    # https://www.w3schools.com/tags/default.asp
    ALL_TAGNAMES = set([
        #"<!--...-->", # Defines a comment
        #"!DOCTYPE", # Defines the document type
        "a", # Defines a hyperlink
        "abbr", # Defines an abbreviation or an acronym
        "address", # Defines contact information for the author/owner of a document
        "area", # Defines an area inside an image map
        "article", # Defines an article
        "aside", # Defines content aside from the page content
        "audio", # Defines embedded sound content
        "b", # Defines bold text
        "base", # Specifies the base URL/target for all relative URLs in a document
        "bdi", # Isolates text that might be formatted in a different direction
        "bdo", # Overrides the current text direction
        "blockquote", # Defines a section quoted from another source
        "body", # Defines the document's body
        "br", # Defines a single line break
        "button", # Defines a clickable button
        "canvas", # Used to draw graphics via scripting
        "caption", # Defines a table caption
        "cite", # Defines the title of a work
        "code", # Defines a piece of computer code
        "col", # Specifies column properties for each column within <colgroup>
        "colgroup", # Specifies a group of columns in a table
        "data", # Adds a machine-readable translation of content
        "datalist", # Specifies a list of pre-defined options for input controls
        "dd", # Defines a description/value in a description list
        "del", # Defines text that has been deleted
        "details", # Defines additional details the user can view/hide
        "dfn", # Specifies a term that is going to be defined
        "dialog", # Defines a dialog box or window
        "div", # Defines a section in a document
        "dl", # Defines a description list
        "dt", # Defines a term/name in a description list
        "em", # Defines emphasized text
        "embed", # Defines a container for an external application
        "fieldset", # Groups related elements in a form
        "figcaption", # Defines a caption for a <figure>
        "figure", # Specifies self-contained content
        "footer", # Defines a footer for a document or section
        "form", # Defines an HTML form for user input
        "h1", # Defines HTML headings
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "head", # Contains metadata/information for the document
        "header", # Defines a header for a document or section
        "hgroup", # Defines a header and related content
        "hr", # Defines a thematic change in content
        "html", # Defines the root of an HTML document
        "i", # Defines text in an alternate voice or mood
        "iframe", # Defines an inline frame
        "img", # Defines an image
        "input", # Defines an input control
        "ins", # Defines text inserted into a document
        "kbd", # Defines keyboard input
        "label", # Defines a label for an input element
        "legend", # Defines a caption for a <fieldset>
        "li", # Defines a list item
        "link", # Defines the relationship between a document and external resource
        "main", # Specifies the main content of a document
        "map", # Defines an image map
        "mark", # Defines highlighted text
        "menu", # Defines an unordered list
        "meta", # Defines metadata about an HTML document
        "meter", # Defines a scalar measurement within a known range
        "nav", # Defines navigation links
        "noscript", # Defines alternate content for users without scripts
        "object", # Defines a container for an external application
        "ol", # Defines an ordered list
        "optgroup", # Defines a group of options in a drop-down list
        "option", # Defines an option in a drop-down list
        "output", # Defines the result of a calculation
        "p", # Defines a paragraph
        "param", # Defines a parameter for an object
        "picture", # Defines a container for multiple image resources
        "pre", # Defines preformatted text
        "progress", # Represents the progress of a task
        "q", # Defines a short quotation
        "rp", # Defines fallback text for ruby annotations
        "rt", # Defines explanation/pronunciation for ruby annotations
        "ruby", # Defines a ruby annotation
        "s", # Defines text that is no longer correct
        "samp", # Defines sample output from a computer program
        "script", # Defines a client-side script
        "search", # Defines a search section
        "section", # Defines a section in a document
        "select", # Defines a drop-down list
        "small", # Defines smaller text
        "source", # Defines media resources for <video>/<audio>
        "span", # Defines a section in a document
        "strong", # Defines important text
        "style", # Defines style information for a document
        "sub", # Defines subscript text
        "summary", # Defines a heading for a <details> element
        "sup", # Defines superscript text
        "svg", # Defines a container for SVG graphics
        "table", # Defines a table
        "tbody", # Groups the body content in a table
        "td", # Defines a cell in a table
        "template", # Defines hidden template content
        "textarea", # Defines a multiline input control
        "tfoot", # Groups footer content in a table
        "th", # Defines a header cell in a table
        "thead", # Groups header content in a table
        "time", # Defines a specific time
        "title", # Defines a title for the document
        "tr", # Defines a row in a table
        "track", # Defines text tracks for media
        "u", # Defines text styled differently
        "ul", # Defines an unordered list
        "var", # Defines a variable
        "video", # Defines embedded video
        "wbr", # Defines a possible line break
    ])

    # https://www.w3schools.com/tags/ref_attributes.asp
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes
    ATTRIBUTES = {
        "Global": set([
            "accesskey", # Keyboard shortcut to activate or add focus to
                         # the element.
            "autocapitalize", # Sets whether input is automatically
                              # capitalized when entered by user
            "class", # Often used with CSS to style elements with common
                     # properties.
            "contenteditable", # Indicates whether the element's content
                               # is editable.
            "data-*", # Lets you attach custom attributes to an HTML
                      # element.
            "dir", # Defines the text direction. Allowed values are ltr
                   # (Left-To-Right) or rtl (Right-To-Left)
            "draggable", # Defines whether the element can be dragged.
            "hidden", # Prevents rendering of given element, while
                      # keeping child elements, e.g. script elements,
                      # active.
            "id", # Often used with CSS to style a specific element. The
                  # value of this attribute must be unique.
            "itemprop",
            "lang", # Defines the language used in the element.
            "role", # Defines an explicit role for an element for use by
                    # assistive technologies.
            "slot", # Assigns a slot in a shadow DOM shadow tree to an
                    # element.
            "spellcheck", # Indicates whether spell checking is allowed
                          # for the element.
            "style", # Defines CSS styles which will override styles
                     # previously set.
            "tabindex", # Overrides the browser's default tab order and
                        # follows the one specified instead.
            "title", # Text to be displayed in a tooltip when hovering
                     # over the element.
            "translate", # Specify whether an element's attribute values
                         # and the values of its Text node children are
                         # to be translated when the page is localized,
                         # or whether to leave them unchanged.
        ]),
        "a": set([
            "download", # Indicates that the hyperlink is to be used for
                        # downloading a resource.
            "href", # The URL of a linked resource.
            "hreflang", # Specifies the language of the linked resource.
            "media", # Specifies a hint of the media for which the
                     # linked resource was designed.
            "ping", # The ping attribute specifies a space-separated
                    # list of URLs to be notified if a user follows the
                    # hyperlink.
            "referrerpolicy", # Specifies which referrer is sent when
                              # fetching the resource.
            "rel", # Specifies the relationship of the target object to
                   # the link object.
            "shape",
            "target", # Specifies where to open the linked document (in
                      # the case of an <a> element) or where to display
                      # the response received (in the case of a <form>
                      # element)
        ]),
        "area": set([
            "alt", # Alternative text in case an image can't be
                   # displayed.
            "coords", # A set of values specifying the coordinates of
                      # the hot-spot region.
            "download", # Indicates that the hyperlink is to be used for
                        # downloading a resource.
            "href", # The URL of a linked resource.
            "media", # Specifies a hint of the media for which the
                     # linked resource was designed.
            "ping", # The ping attribute specifies a space-separated
                    # list of URLs to be notified if a user follows the
                    # hyperlink.
            "referrerpolicy", # Specifies which referrer is sent when
                              # fetching the resource.
            "rel", # Specifies the relationship of the target object to
                   # the link object.
            "shape",
            "target", # Specifies where to open the linked document (in
                      # the case of an <a> element) or where to display
                      # the response received (in the case of a <form>
                      # element)
        ]),
        "audio": set([
            "autoplay", # The audio or video should play as soon as
                        # possible.
            "controls", # Indicates whether the browser should show
                        # playback controls to the user.
            "crossorigin", # How the element handles cross-origin
                           # requests
            "loop", # Indicates whether the media should start playing
                    # from the start when it's finished.
            "muted", # Indicates whether the audio will be initially
                     # silenced on page load.
            "preload", # Indicates whether the whole resource, parts of
                       # it or nothing should be preloaded.
            "src", # The URL of the embeddable content.
        ]),
        "base": set([
            "href", # The URL of a linked resource.
            "target", # Specifies where to open the linked document (in
                      # the case of an <a> element) or where to display
                      # the response received (in the case of a <form>
                      # element)
        ]),
        "blockquote": set([
            "cite", # Contains a URI which points to the source of the
                    # quote or change.
        ]),
        "body": set([
            "background", # Specifies the URL of an image file. Note:
                          # Although browsers and email clients may
                          # still support this attribute, it is
                          # obsolete. Use CSS background-image instead.
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
        ]),
        "button": set([
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "form", # Indicates the form that is the owner of the
                    # element.
            "formaction", # Indicates the action of the element,
                          # overriding the action defined in the <form>.
            "formenctype", # If the button/input is a submit button
                           # (e.g., type="submit"), this attribute sets
                           # the encoding type to use during form
                           # submission. If this attribute is specified,
                           # it overrides the enctype attribute of the
                           # button's form owner.
            "formmethod", # If the button/input is a submit button
                          # (e.g., type="submit"), this attribute sets
                          # the submission method to use during form
                          # submission (GET, POST, etc.). If this
                          # attribute is specified, it overrides the
                          # method attribute of the button's form owner.
            "formnovalidate", # If the button/input is a submit button
                              # (e.g., type="submit"), this boolean
                              # attribute specifies that the form is not
                              # to be validated when it is submitted. If
                              # this attribute is specified, it
                              # overrides the novalidate attribute of
                              # the button's form owner.
            "formtarget", # If the button/input is a submit button
                          # (e.g., type="submit"), this attribute
                          # specifies the browsing context (for example,
                          # tab, window, or inline frame) in which to
                          # display the response that is received after
                          # submitting the form. If this attribute is
                          # specified, it overrides the target attribute
                          # of the button's form owner.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "type", # Defines the type of the element.
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "canvas": set([
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
        "col": set([
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
            "span",
        ]),
        "colgroup": set([
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
            "span",
        ]),
        "data": set([
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "del": set([
            "cite", # Contains a URI which points to the source of the
                    # quote or change.
            "datetime", # Indicates the date and time associated with
                        # the element.
        ]),
        "details": set([
            "open", # Indicates whether the contents are currently
                    # visible (in the case of a <details> element) or
                    # whether the dialog is active and can be interacted
                    # with (in the case of a <dialog> element).
        ]),
        "dialog": set([
            "open", # Indicates whether the contents are currently
                    # visible (in the case of a <details> element) or
                    # whether the dialog is active and can be interacted
                    # with (in the case of a <dialog> element).
        ]),
        "embed": set([
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "src", # The URL of the embeddable content.
            "type", # Defines the type of the element.
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
        "fieldset": set([
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "form", # Indicates the form that is the owner of the
                    # element.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
        ]),
        "font": set([
            "color", # This attribute sets the text color using either a
                     # named color or a color specified in the
                     # hexadecimal #RRGGBB format. Note: This is a
                     # legacy attribute. Please use the CSS color
                     # property instead.
        ]),
        "form": set([
            "accept", # List of types the server accepts, typically a
                      # file type.
            "accept-charset", # The character set, which if provided
                              # must be "UTF-8".
            "action", # The URI of a program that processes the
                      # information submitted via the form.
            "autocomplete", # Indicates whether controls in this form
                            # can by default have their values
                            # automatically completed by the browser.
            "enctype", # Defines the content type of the form data when
                       # the method is POST.
            "method", # Defines which HTTP method to use when submitting
                      # the form. Can be GET (default) or POST.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "novalidate", # This attribute indicates that the form
                          # shouldn't be validated when submitted.
            "target", # Specifies where to open the linked document (in
                      # the case of an <a> element) or where to display
                      # the response received (in the case of a <form>
                      # element)
        ]),
        "hr": set([
            "color", # This attribute sets the text color using either a
                     # named color or a color specified in the
                     # hexadecimal #RRGGBB format. Note: This is a
                     # legacy attribute. Please use the CSS color
                     # property instead.
        ]),
        "iframe": set([
            "allow", # Specifies a feature-policy for the iframe.
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "loading", # Indicates if the element should be loaded
                       # lazily (loading="lazy") or loaded immediately
                       # (loading="eager").
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "referrerpolicy", # Specifies which referrer is sent when
                              # fetching the resource.
            "sandbox", # Stops a document loaded in an iframe from using
                       # certain features (such as submitting forms or
                       # opening new windows).
            "src", # The URL of the embeddable content.
            "srcdoc",
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
        "image": set([
            "elementtiming", # Indicates that an element is flagged for
                             # tracking by PerformanceObserver objects
                             # using the "element" type. For more
                             # details, see the PerformanceElementTiming
                             # interface.
        ]),
        "img": set([
            "alt", # Alternative text in case an image can't be
                   # displayed.
            "border", # The border width.Note: This is a legacy
                      # attribute. Please use the CSS border property
                      # instead.
            "crossorigin", # How the element handles cross-origin
                           # requests
            "decoding", # Indicates the preferred method to decode the
                        # image.
            "elementtiming", # Indicates that an element is flagged for
                             # tracking by PerformanceObserver objects
                             # using the "element" type. For more
                             # details, see the PerformanceElementTiming
                             # interface.
            "fetchpriority", # Signals that fetching a particular image
                             # early in the loading process has more or
                             # less impact on user experience than a
                             # browser can reasonably infer when
                             # assigning an internal priority.
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "ismap", # Indicates that the image is part of a server-side
                     # image map.
            "loading", # Indicates if the element should be loaded
                       # lazily (loading="lazy") or loaded immediately
                       # (loading="eager").
            "referrerpolicy", # Specifies which referrer is sent when
                              # fetching the resource.
            "sizes",
            "src", # The URL of the embeddable content.
            "srcset", # One or more responsive image candidates.
            "usemap",
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
        "input": set([
            "accept", # List of types the server accepts, typically a
                      # file type.
            "alpha", # Allow the user to select a color's opacity on a
                     # type="color" input.
            "alt", # Alternative text in case an image can't be
                   # displayed.
            "autocomplete", # Indicates whether controls in this form
                            # can by default have their values
                            # automatically completed by the browser.
            "capture", # From the Media Capture specification, specifies
                       # a new file can be captured.
            "checked", # Indicates whether the element should be checked
                       # on page load.
            "colorspace", # Defines the color space that is used by a
                          # type="color" input.
            "dirname",
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "form", # Indicates the form that is the owner of the
                    # element.
            "formaction", # Indicates the action of the element,
                          # overriding the action defined in the <form>.
            "formenctype", # If the button/input is a submit button
                           # (e.g., type="submit"), this attribute sets
                           # the encoding type to use during form
                           # submission. If this attribute is specified,
                           # it overrides the enctype attribute of the
                           # button's form owner.
            "formmethod", # If the button/input is a submit button
                          # (e.g., type="submit"), this attribute sets
                          # the submission method to use during form
                          # submission (GET, POST, etc.). If this
                          # attribute is specified, it overrides the
                          # method attribute of the button's form owner.
            "formnovalidate", # If the button/input is a submit button
                              # (e.g., type="submit"), this boolean
                              # attribute specifies that the form is not
                              # to be validated when it is submitted. If
                              # this attribute is specified, it
                              # overrides the novalidate attribute of
                              # the button's form owner.
            "formtarget", # If the button/input is a submit button
                          # (e.g., type="submit"), this attribute
                          # specifies the browsing context (for example,
                          # tab, window, or inline frame) in which to
                          # display the response that is received after
                          # submitting the form. If this attribute is
                          # specified, it overrides the target attribute
                          # of the button's form owner.
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "list", # Identifies a list of pre-defined options to
                    # suggest to the user.
            "max", # Indicates the maximum value allowed.
            "maxlength", # Defines the maximum number of characters
                         # allowed in the element.
            "minlength", # Defines the minimum number of characters
                         # allowed in the element.
            "min", # Indicates the minimum value allowed.
            "multiple", # Indicates whether multiple values can be
                        # entered in an input of the type email or file.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "pattern", # Defines a regular expression which the
                       # element's value will be validated against.
            "placeholder", # Provides a hint to the user of what can be
                           # entered in the field.
            "readonly", # Indicates whether the element can be edited.
            "required", # Indicates whether this element is required to
                        # fill out or not.
            "size", # Defines the width of the element (in pixels). If
                    # the element's type attribute is text or password
                    # then it's the number of characters.
            "src", # The URL of the embeddable content.
            "step",
            "type", # Defines the type of the element.
            "usemap",
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
        "ins": set([
            "cite", # Contains a URI which points to the source of the
                    # quote or change.
            "datetime", # Indicates the date and time associated with
                        # the element.
        ]),
        "label": set([
            "for", # Describes elements which belongs to this one.
        ]),
        "li": set([
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "link": set([
            "as", # Specifies the type of content being loaded by the
                  # link.
            "crossorigin", # How the element handles cross-origin
                           # requests
            "fetchpriority", # Signals that fetching a particular image
                             # early in the loading process has more or
                             # less impact on user experience than a
                             # browser can reasonably infer when
                             # assigning an internal priority.
            "href", # The URL of a linked resource.
            "hreflang", # Specifies the language of the linked resource.
            "integrity", # Specifies a Subresource Integrity value that
                         # allows browsers to verify what they fetch.
            "media", # Specifies a hint of the media for which the
                     # linked resource was designed.
            "referrerpolicy", # Specifies which referrer is sent when
                              # fetching the resource.
            "rel", # Specifies the relationship of the target object to
                   # the link object.
            "sizes",
            "type", # Defines the type of the element.
        ]),
        "map": set([
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
        ]),
        "marquee": set([
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
            "loop", # Indicates whether the media should start playing
                    # from the start when it's finished.
        ]),
        "menu": set([
            "type", # Defines the type of the element.
        ]),
        "meta": set([
            "charset", # Declares the character encoding of the page or
                       # script.
            "content", # A value associated with http-equiv or name
                       # depending on the context.
            "http-equiv", # Defines a pragma directive.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
        ]),
        "meter": set([
            "high", # Indicates the lower bound of the upper range.
            "low", # Indicates the upper bound of the lower range.
            "max", # Indicates the maximum value allowed.
            "min", # Indicates the minimum value allowed.
            "optimum", # Indicates the optimal numeric value.
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "object": set([
            "border", # The border width.Note: This is a legacy
                      # attribute. Please use the CSS border property
                      # instead.
            "data", # Specifies the URL of the resource.
            "form", # Indicates the form that is the owner of the
                    # element.
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "type", # Defines the type of the element.
            "usemap",
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
        "ol": set([
            "reversed", # Indicates whether the list should be displayed
                        # in a descending order instead of an ascending
                        # order.
            "start", # Defines the first number if other than 1.
            "type", # Defines the type of the element.
        ]),
        "optgroup": set([
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "label", # Specifies a user-readable title of the element.
        ]),
        "option": set([
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "label", # Specifies a user-readable title of the element.
            "selected", # Defines a value which will be selected on page
                        # load.
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "output": set([
            "for", # Describes elements which belongs to this one.
            "form", # Indicates the form that is the owner of the
                    # element.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
        ]),
        "p": set([
            "elementtiming", # Indicates that an element is flagged for
                             # tracking by PerformanceObserver objects
                             # using the "element" type. For more
                             # details, see the PerformanceElementTiming
                             # interface.
        ]),
        "param": set([
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "progress": set([
            "max", # Indicates the maximum value allowed.
            "value", # Defines a default value which will be displayed
                     # in the element on page load.
        ]),
        "q": set([
            "cite", # Contains a URI which points to the source of the
                    # quote or change.
        ]),
        "script": set([
            "async", # Executes the script asynchronously.
            "crossorigin", # How the element handles cross-origin
                           # requests
            "defer", # Indicates that the script should be executed
                     # after the page has been parsed.
            "fetchpriority", # Signals that fetching a particular image
                             # early in the loading process has more or
                             # less impact on user experience than a
                             # browser can reasonably infer when
                             # assigning an internal priority.
            "integrity", # Specifies a Subresource Integrity value that
                         # allows browsers to verify what they fetch.
            "referrerpolicy", # Specifies which referrer is sent when
                              # fetching the resource.
            "src", # The URL of the embeddable content.
            "type", # Defines the type of the element.
        ]),
        "select": set([
            "autocomplete", # Indicates whether controls in this form
                            # can by default have their values
                            # automatically completed by the browser.
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "form", # Indicates the form that is the owner of the
                    # element.
            "multiple", # Indicates whether multiple values can be
                        # entered in an input of the type email or file.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "required", # Indicates whether this element is required to
                        # fill out or not.
            "size", # Defines the width of the element (in pixels). If
                    # the element's type attribute is text or password
                    # then it's the number of characters.
        ]),
        "source": set([
            "media", # Specifies a hint of the media for which the
                     # linked resource was designed.
            "sizes",
            "src", # The URL of the embeddable content.
            "srcset", # One or more responsive image candidates.
            "type", # Defines the type of the element.
        ]),
        "style": set([
            "media", # Specifies a hint of the media for which the
                     # linked resource was designed.
            "type", # Defines the type of the element.
        ]),
        "svg": set([
            "elementtiming", # Indicates that an element is flagged for
                             # tracking by PerformanceObserver objects
                             # using the "element" type. For more
                             # details, see the PerformanceElementTiming
                             # interface.
        ]),
        "table": set([
            "background", # Specifies the URL of an image file. Note:
                          # Although browsers and email clients may
                          # still support this attribute, it is
                          # obsolete. Use CSS background-image instead.
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
            "border", # The border width.Note: This is a legacy
                      # attribute. Please use the CSS border property
                      # instead.
        ]),
        "tbody": set([
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
        ]),
        "td": set([
            "background", # Specifies the URL of an image file. Note:
                          # Although browsers and email clients may
                          # still support this attribute, it is
                          # obsolete. Use CSS background-image instead.
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
            "colspan", # The colspan attribute defines the number of
                       # columns a cell should span.
            "headers", # IDs of the <th> elements which applies to this
                       # element.
            "rowspan", # Defines the number of rows a table cell should
                       # span over.
        ]),
        "textarea": set([
            "autocomplete", # Indicates whether controls in this form
                            # can by default have their values
                            # automatically completed by the browser.
            "cols", # Defines the number of columns in a textarea.
            "dirname",
            "disabled", # Indicates whether the user can interact with
                        # the element.
            "enterkeyhint", # The enterkeyhint specifies what action
                            # label (or icon) to present for the enter
                            # key on virtual keyboards. The attribute
                            # can be used with form controls (such as
                            # the value of textarea elements), or in
                            # elements in an editing host (e.g., using
                            # contenteditable attribute).
            "form", # Indicates the form that is the owner of the
                    # element.
            "inputmode", # Provides a hint as to the type of data that
                         # might be entered by the user while editing
                         # the element or its contents. The attribute
                         # can be used with form controls (such as the
                         # value of textarea elements), or in elements
                         # in an editing host (e.g., using
                         # contenteditable attribute).
            "maxlength", # Defines the maximum number of characters
                         # allowed in the element.
            "minlength", # Defines the minimum number of characters
                         # allowed in the element.
            "name", # Name of the element. For example used by the
                    # server to identify the fields in form submits.
            "placeholder", # Provides a hint to the user of what can be
                           # entered in the field.
            "readonly", # Indicates whether the element can be edited.
            "required", # Indicates whether this element is required to
                        # fill out or not.
            "rows", # Defines the number of rows in a text area.
            "wrap", # Indicates whether the text should be wrapped.
        ]),
        "tfoot": set([
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
        ]),
        "th": set([
            "background", # Specifies the URL of an image file. Note:
                          # Although browsers and email clients may
                          # still support this attribute, it is
                          # obsolete. Use CSS background-image instead.
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
            "colspan", # The colspan attribute defines the number of
                       # columns a cell should span.
            "headers", # IDs of the <th> elements which applies to this
                       # element.
            "rowspan", # Defines the number of rows a table cell should
                       # span over.
            "scope", # Defines the cells that the header test (defined
                     # in the th element) relates to.
        ]),
        "time": set([
            "datetime", # Indicates the date and time associated with
                        # the element.
        ]),
        "tr": set([
            "bgcolor", # Background color of the element.Note: This is a
                       # legacy attribute. Please use the CSS
                       # background-color property instead.
        ]),
        "track": set([
            "default", # Indicates that the track should be enabled
                       # unless the user's preferences indicate
                       # something different.
            "kind", # Specifies the kind of text track.
            "label", # Specifies a user-readable title of the element.
            "src", # The URL of the embeddable content.
            "srclang",
        ]),
        "video": set([
            "autoplay", # The audio or video should play as soon as
                        # possible.
            "controls", # Indicates whether the browser should show
                        # playback controls to the user.
            "crossorigin", # How the element handles cross-origin
                           # requests
            "elementtiming", # Indicates that an element is flagged for
                             # tracking by PerformanceObserver objects
                             # using the "element" type. For more
                             # details, see the PerformanceElementTiming
                             # interface.
            "height", # Specifies the height of elements listed here.
                      # For all other elements, use the CSS height
                      # property. Note: In some instances, such as
                      # <div>, this is a legacy attribute, in which case
                      # the CSS height property should be used instead.
            "loop", # Indicates whether the media should start playing
                    # from the start when it's finished.
            "muted", # Indicates whether the audio will be initially
                     # silenced on page load.
            "playsinline", # A Boolean attribute indicating that the
                           # video is to be played "inline"; that is,
                           # within the element's playback area. Note
                           # that the absence of this attribute does not
                           # imply that the video will always be played
                           # in fullscreen.
            "poster", # A URL indicating a poster frame to show until
                      # the user plays or seeks.
            "preload", # Indicates whether the whole resource, parts of
                       # it or nothing should be preloaded.
            "src", # The URL of the embeddable content.
            "width", # For the elements listed here, this establishes
                     # the element's width. Note: For all other
                     # instances, such as <div>, this is a legacy
                     # attribute, in which case the CSS width property
                     # should be used instead.
        ]),
    }

    def plain(self, **kwargs):
        hc = kwargs.pop("cleaner_class", HTMLCleaner)(**kwargs)
        return hc.feed(self)

    def inject_into_head(self, html):
        """Inject passed in html into head

        Moved from bang.utils on 1-6-2023

        :param html: str, the html that will be injected to the head tag of
            self
        :returns: HTML, a new HTML string with the injected html
        """
        def callback(m):
            return "{}{}{}".format(m.group(1), html, m.group(0))

        regex = r"(\s*)(</head>)"
        ret = re.sub(regex, callback, self, flags=re.I|re.M)
        return type(self)(ret)

    def inject_into_body(self, html):
        """Inject passed in html into body

        Moved from bang.utils on 1-6-2023

        :param html: str, the html that will be injected to the body tag of
            self
        :returns: HTML, a new HTML string with the injected html
        """
        def callback(m):
            return "{}{}{}".format(m.group(1), html, m.group(0))

        regex = r"(\s*)(</body>)"
        ret = re.sub(regex, callback, self, flags=re.I|re.M)
        return type(self)(ret)

    def strip_tags(self, strip_tagnames=None, **kwargs):
        """Strip tags, completely removing any tags in remove_tags list

        This is different than `.plain()` in that only the html tags that
        in `strip_tagnames` are completely removed, all other html tags
        remain intact

        Moved from bang.utils on 1-6-2023

        http://stackoverflow.com/a/925630

        :param strip_tagnames: list[str], a list of tags that will be
        completely removed from the html
        :returns: str, the html with tags in `strip_tagnames` completely
            removed
        """
        hc = kwargs.pop("cleaner_class", HTMLCleaner)(
            ignore_tagnames=True,
            strip_tagnames=strip_tagnames
        )
        return hc.feed(self)

    def blocks(self, *, ignore_tagnames=None, **kwargs):
        """Tokenize the html into blocks. This is tough to describe so go
        read the description on the html block iterator this returns

        :returns: HTMLBlockTokenizer
        """
        tokenizer_class = kwargs.get("tokenizer_class", HTMLBlockTokenizer)
        return tokenizer_class(self, ignore_tagnames=ignore_tagnames)


class HTMLCleaner(HTMLParser):
    """Internal class. Can turn html to plain text, completely remove
    certain tags, or both

    .. Example:
        # convert html to plain text
        html = "this is <b>some html</b>
        text = HTMLCleaner().feed(html)
        print(text) # this is some html

        # strip certain tags from the html
        html = "<p>this is some <span>fancy text</span> stuff</p>"
        text = HTMLCleaner(
            ignore_tagnames=True,
            strip_tagnames=["span"]
        ).feed(html)
        print(text) # <p>this is some stuff</p>

    http://stackoverflow.com/a/925630/5006
    https://docs.python.org/3/library/html.parser.html
    """
    def __init__(
        self,
        *,
        ignore_tagnames=None,
        strip_tagnames=None,
        block_sep="\n",
        inline_sep="",
        keep_img_src=False,
        **kwargs
    ):
        """create an instance and configure it

        :keyword ignore_tagnames: Collection[str]|bool|None, the list of
            tagnames to not clean, either a list of tagnames (eg ["a"]) or
            True. If True, then all tags will be ignored except the tags in
            `strip_tagnames`
        :keyword strip_tagnames: Collection[str]|None, the list of tags to
            be completely stripped out (everything from the opening <TAGNAME
            to the closing </TAGNAME> will be removed)
        :keyword block_sep: string, strip a block tag and then add this to the
            end of the stripped tag, so if you have <p>foo bar<p> and
            block_sep=\n, then the stripped string would be foo bar\n
        :keyword inline_sep: string, same as block_sep, but gets added to the
            end of the stripped inline tag
        :keyword keep_img_src: boolean, if True, the img.src attribute will
            replace the full <img /> tag, this is nice when you want plain
            text but want to keep knowledge of the images that were in the
            original html
        """
        if ignore_tagnames is True:
            self.ignore_tagnames = ignore_tagnames

        else:
            self.ignore_tagnames = self._normalize_tagnames(ignore_tagnames)

        self.strip_tagnames = self._normalize_tagnames(strip_tagnames)

        self.block_sep = block_sep
        self.inline_sep = inline_sep
        self.keep_img_src = keep_img_src

        super().__init__(**kwargs)

    def reset(self):
        self.cleaned_html = ""
        self.stripping_tagnames_stack = []
        self.stripping_tags = Counter()

        super().reset()

    def feed(self, data) -> str:
        """process `data` based on the instance flags

        :returns: str, the processed/cleaned data
        """
        self.cleaned_html = ""

        super().feed(data)

        return self.cleaned_html

    def close(self) -> str:
        """Finish processing any data left in the buffer and return the
        cleaned buffer

        :returns: str, the processed/cleaned buffer
        """
        self.cleaned_html = ""

        super().close()

        return self.cleaned_html

    def _normalize_tagnames(self, tagnames) -> set[str]:
        tnames = set()

        if tagnames:
            tnames.update(map(lambda s: s.lower(), tagnames))

        return tnames

    def _in_tagnames(self, tagname, attrs, tagnames) -> bool:
        """Check if `tagnames` is in `tagnames`.

        Uses `attrs` for simple css selector support (eg, `div.foo` to match
        div tags with the `foo` class, and `div#foo` to match div tags with
        the `foo` id)

        :param tagname: str
        :param attrs: list[tuple[str, str]]
        :param tagnames: set, usually the value returned from
            `._normalize_tagnames()`
        """
        ret = False

        if tagnames:
            if tagname in tagnames:
                ret = True

            else:
                # really basic css selector support
                for k, v in attrs:
                    if k == "class":
                        selector = "{}.{}".format(tagname, v)
                        if selector in tagnames:
                            ret = True
                            break

                    elif k == "id":
                        selector = "{}#{}".format(tagname, v)
                        if selector in tagnames:
                            ret = True
                            break

        return ret

    def _is_ignored(self, tagname, attrs=None) -> bool:
        """Return True if tagname should be ignored"""
        if self.ignore_tagnames is True:
            return True

        else:
            return self._in_tagnames(
                tagname,
                attrs or [],
                self.ignore_tagnames
            )

    def _is_stripped(self, tagname, attrs=None) -> bool:
        """Return True if tagname should be completely stripped"""
        return self._in_tagnames(
            tagname,
            attrs or [],
            self.strip_tagnames
        )

    def handle_data(self, data):
        if not self.stripping_tags:
        #if not self.stripping_tagnames_stack:
            self.cleaned_html += data

    def handle_entityref(self, name):
        """keep entityrefs as they were

        https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_entityref
        > This method is never called if convert_charrefs is True
        """
        entity = f"&{name};"
        self.cleaned_html += entity

    def handle_starttag(self, tagname, attrs):
        # https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag

        if self._is_stripped(tagname, attrs):
            self.stripping_tags[tagname] += 1
            #self.stripping_tagnames_stack.append(tagname)

        else:
            if not self.stripping_tags:
                if self._is_ignored(tagname, attrs):
                    self.cleaned_html += self.get_starttag_text()

                else:
                    if tagname == "img" and self.keep_img_src:
                        for attr_name, attr_val in attrs:
                            if attr_name == "src":
                                self.cleaned_html += "{}{}".format(
                                    self.block_sep,
                                    attr_val
                                )

    def handle_endtag(self, tagname):
        if self.stripping_tags:
            if tagname in self.stripping_tags:
                self.stripping_tags[tagname] -= 1
                if self.stripping_tags[tagname] == 0:
                    del self.stripping_tags[tagname]

        else:
            if self._is_ignored(tagname):
                self.cleaned_html += f"</{tagname}>"

            else:
                if tagname in HTML.BLOCK_TAGNAMES:
                    self.cleaned_html += self.block_sep

                else:
                    if tagname == "img" and self.keep_img_src:
                        self.cleaned_html += self.block_sep

                    else:
                        self.cleaned_html += self.inline_sep


class HTMLBlockTokenizer(Iterable):
    """Internal class. Iterate through blocks of html and the inner text of
    the element.

    The way to describe this is that everything this iterates would equal
    the original input if it was all concatenated together.

    .. Example:
        html = HTMLBlockTokenizer(
            "before all"
            " <p>after p before a "
            " <a href=\"#\">between a</a>"
            " after a</p>"
            " after all"
        )

        blocks = ""
        for element in html:
            # ("", "before all")
            # ("<p>", "after p before a")
            # ("<a href="#">", "between a")
            # ("</a>", "after a")
            # ("</p>", "after all")
            blocks += element[0]
            blocks += element[1]

        assert blocks == html

    Now, if you pass any tags into `ignore_tagnames` then the first element
    of the tuple will be the full value of that tag

    .. Example:
        html = HTMLBlockTokenizer(
            (
                " <p>after p before a "
                " <a href=\"#\">between a</a>"
                " after a</p>"
            ),
            ignore_tagnames=["a"]
        )

        blocks = ""
        for element in html:
            # ("<p>", "after p before a")
            # ("<a href="#">between a</a>", "after a")
            # ("</p>", "")
            blocks += element[0]
            blocks += element[1]

        assert blocks == html

    This allows for things like getting all the plain text bodies for further
    processing, like automatically linking URLs and not having to worry with
    linking things that are already linked. I know that might seem niche but
    I've had to do this exact thing in multiple projects throughout the
    years.

    Moved from bang.utils on 1-6-2023, fleshed out and integrated into HTML
    on 3-3-2025
    """
    def __init__(self, html, *, ignore_tagnames=None, **kwargs):
        """Create a block tokenizer

        :param html: str|io.IOBase, the html that is going to be split into
            blocks
        :keyword ignore_tagnames: Collection, the list/set of tag names that
            should be ignored (eg, ["a", "pre"])
        :keyword scanner_class: Scanner
        """
        self.scanner = kwargs.get("scanner_class", Scanner)(html)

        self.ignore_start_set = set()
        self.ignore_stop_set = set()

        if ignore_tagnames:
            for tagname in ignore_tagnames:
                self.ignore_start_set.add(f"<{tagname}>")
                self.ignore_start_set.add(f"<{tagname} ")
                self.ignore_stop_set.add(f"</{tagname}>")

    def _startswith_tagname(self, html) -> bool:
        """Internal method. Used to see if the html starts with an ignored
        tag name"""
        for tag in self.ignore_start_set:
            if html.startswith(tag):
                return True

        return False

    def _endswith_tagname(self, html) -> bool:
        """Internal method. Used to see if the html ends with an ignored
        tag name"""
        for tag in self.ignore_stop_set:
            if html.endswith(tag):
                return True

        return False

    def __iter__(self) -> Iterable[tuple[str, str]]:
        """returns plain text blocks that aren't in html tags

        :returns: each tuple is the html tag and then the inner html of that
            tag
        """
        s = self.scanner
        html = ""
        plain = s.read_to(delim="<")
        while True:
            if html or plain:
                yield html, plain

            html = s.read_to(
                delim=">",
                ignore_between_delims=["\"", "'"],
                include_delim=True
            )
            if html:
                plain = s.read_to(delim="<")
                if self._startswith_tagname(html):
                    while not self._endswith_tagname(html):
                        html += plain
                        h = s.read_to(delim=">", include_delim=True)
                        plain = s.read_to(delim="<")

                        if h or plain:
                            html += h

                        else:
                            # we've reached EOF
                            break

            if not html:
                # we've reached the end of the file
                break

