from collective.plonetruegallery.interfaces import IDisplayType
from collective.plonetruegallery.interfaces import IBatchingDisplayType
from collective.plonetruegallery.interfaces import IS3sliderDisplaySettings
from collective.plonetruegallery.interfaces import \
    IThumbnailzoomDisplaySettings
from collective.plonetruegallery.interfaces import \
    ISupersizedDisplaySettings
from plone.memoize.view import memoize
from zope.interface import implements
from collective.plonetruegallery import PTGMessageFactory as _
from collective.plonetruegallery.settings import GallerySettings
from Products.CMFPlone.PloneBatch import Batch
from zope.component import getMultiAdapter
from Products.Five import BrowserView
from collective.plonetruegallery.utils import getGalleryAdapter
from collective.plonetruegallery.utils import createSettingsFactory
try:
    import json
except ImportError:
    import simplejson as json


def jsbool(val):
    return str(val).lower()


class BaseDisplayType(BrowserView):
    implements(IDisplayType)

    name = None
    description = None
    schema = None
    userWarning = None
    staticFilesRelative = '++resource++plonetruegallery.resources'
    typeStaticFilesRelative = ''

    def __init__(self, context, request):
        super(BaseDisplayType, self).__init__(context, request)
        self.adapter = getGalleryAdapter(context, request)
        self.context = self.gallery = self.adapter.gallery
        self.settings = GallerySettings(context,
                            interfaces=[self.adapter.schema, self.schema])
        portal_state = getMultiAdapter((context, request),
                                        name='plone_portal_state')
        self.portal_url = portal_state.portal_url()
        self.staticFiles = "%s/%s" % (self.portal_url,
                                      self.staticFilesRelative)
        self.typeStaticFiles = '%s/%s' % (self.portal_url,
                                          self.typeStaticFilesRelative)

    def content(self):
        return self.index()

    @property
    def height(self):
        return self.adapter.sizes[self.settings.size]['height']

    @property
    def width(self):
        return self.adapter.sizes[self.settings.size]['width']

    @memoize
    def get_start_image_index(self):
        if 'start_image' in self.request:
            si = self.request.get('start_image', '')
            images = self.adapter.cooked_images
            for index in range(0, len(images)):
                if si == images[index]['title']:
                    return index
        return 0

    start_image_index = property(get_start_image_index)

    def css(self):
        return ''

    def javascript(self):
        return ''


class BatchingDisplayType(BaseDisplayType):
    implements(IDisplayType, IBatchingDisplayType)

    @memoize
    def uses_start_image(self):
        """
        disable start image if a batch start is specified.
        """
        return bool('start_image' in self.request) and \
            not bool('b_start' in self.request)

    @memoize
    def get_b_start(self):
        if self.uses_start_image():
            page = self.get_page()
            return page * self.settings.batch_size
        else:
            return int(self.request.get('b_start', 0))

    b_start = property(get_b_start)

    @memoize
    def get_start_image_index(self):
        if self.uses_start_image():
            index = super(BatchingDisplayType, self).get_start_image_index()
            return index - (self.get_page() * self.settings.batch_size)
        else:
            return 0

    start_image_index = property(get_start_image_index)

    @memoize
    def get_page(self):
        index = super(BatchingDisplayType, self).get_start_image_index()
        return index / self.settings.batch_size

    @property
    @memoize
    def start_automatically(self):
        return self.uses_start_image() or \
            self.adapter.number_of_images < self.settings.batch_size

    @property
    @memoize
    def batch(self):
        return Batch(self.adapter.cooked_images, self.settings.batch_size,
                                              int(self.b_start), orphan=1)


class S3sliderDisplayType(BaseDisplayType):

    name = u"s3slider"
    schema = IS3sliderDisplaySettings
    description = _(u"label_s3slider_display_type",
        default=u"s3slider")

    def javascript(self):
        return u"""
<script type="text/javascript"
    src="%(portal_url)s/++resource++s3Slider.js"></script>

<script type="text/javascript">
$(document).ready(function() {
   $('#s3slider').s3Slider({
      timeOut: %(delay)i
   });
})(jQuery);
</script>
        """ % {
        'portal_url': self.portal_url,
        'delay': self.settings.delay
        }

    def css(self):
        base = '%s/++resource++plonetruegallery.resources/s3slider' % (
            self.portal_url)
        style = '%(base)s/%(style)s' % {
                'base' : base, 
                'style' : self.settings.s3slider_style}

        if self.settings.s3slider_style == 'custom_style':
            style = '%(url)s/%(style)s' % {
                'url': self.portal_url,
                'style': self.settings.s3slider_custom_style}

        return u"""
        <style>
#s3slider {
   height: %(height)s;
   width: %(width)s;
   position: relative;
   overflow: hidden;
}

ul#s3sliderContent {
   width: %(width)s;
}
</style>
<link rel="stylesheet" type="text/css" href="%(style)s"/>
""" % {
        'staticFiles': self.staticFiles,
        'height': self.settings.s3_height,
        'width': self.settings.s3_width,
        'textwidth': self.settings.s3_textwidth,
        'style': style,
       }

S3sliderSettings = createSettingsFactory(S3sliderDisplayType.schema)


class ThumbnailzoomDisplayType(BatchingDisplayType):
    name = u"thumbnailzoom"
    schema = IThumbnailzoomDisplaySettings
    description = _(u"label_thumbnailzoom_display_type",
        default=u"Thumbnailzoom")

    def javascript(self):
        return u"""
<script type="text/javascript" charset="utf-8">
$(window).load(function(){
    //set and get some variables
    var thumbnail = {
        imgIncrease : %(increase)i,
        effectDuration : %(effectduration)i,
        imgWidth : $('.thumbnailWrapper ul li').find('img').width(),
        imgHeight : $('.thumbnailWrapper ul li').find('img').height()
    };

    //make the list items same size as the images
    $('.thumbnailWrapper ul li').css({
        'width' : thumbnail.imgWidth,
        'height' : thumbnail.imgHeight
    });

    //when mouse over the list item...
    $('.thumbnailWrapper ul li').hover(function(){
        $(this).find('img').stop().animate({
            /* increase the image width for the zoom effect*/
            width: parseInt(thumbnail.imgWidth) + thumbnail.imgIncrease,
            /* we need to change the left and top position in order to
            have the zoom effect, so we are moving them to a negative
            position of the half of the imgIncrease */
            left: thumbnail.imgIncrease/2*(-1),
            top: thumbnail.imgIncrease/2*(-1)
        },{
            "duration": thumbnail.effectDuration,
            "queue": false
        });
        //show the caption using slideDown event
        $(this).find('.caption:not(:animated)').slideDown(
            thumbnail.effectDuration);
    //when mouse leave...
    }, function(){
        //find the image and animate it...
        $(this).find('img').animate({
            /* get it back to original size (zoom out) */
            width: thumbnail.imgWidth,
            /* get left and top positions back to normal */
            left: 0,
            top: 0
        }, thumbnail.effectDuration);
        //hide the caption using slideUp event
        $(this).find('.caption').slideUp(thumbnail.effectDuration);
    });
});
</script>
""" % {
    'increase': self.settings.thumbnailzoom_increase,
    'effectduration': self.settings.thumbnailzoom_effectduration,
}

    def css(self):
        style = '%s/thumbnailzoom/%s' % (
            self.staticFiles, self.settings.thumbnailzoom_style)

        if self.settings.thumbnailzoom_style == 'custom_style':
            style = '%s/%s' % (
                self.portal_url, self.settings.thumbnailzoom_custom_style)

        return u"""
<link rel="stylesheet" type="text/css" href="%s"/>
""" % style
ThumbnailzoomSettings = createSettingsFactory(ThumbnailzoomDisplayType.schema)


class SupersizedDisplayType(BaseDisplayType):
    name = u"supersized"
    schema = ISupersizedDisplaySettings
    description = _(u"label_supersized_display_type",
        default=u"Supersized")

    def css(self):
        return u"""
        <style>%(supersized_css)s</style>
<link rel="stylesheet" type="text/css"
    href="%(portal_url)s/++resource++supersized.css"/>
<link rel="stylesheet" type="text/css"
    href="%(portal_url)s/++resource++supersized.shutter.css"/>
""" % {
    'portal_url': self.portal_url,
    'supersized_css': self.settings.supersized_css
    }

    def javascript(self):
        """  this code looks quite ugly...
        The image part for the javascript is constructed below
        and used in the 'slides' : %(imagelist)s
        """
        images = self.adapter.cooked_images
        imagelist = []
        for image in images:
            imagelist.append({
                'image': image['image_url'],
                'title': image['title'],
                'thumb': image['thumb_url'],
                'url': image['link']
                })

        return u"""
<script type="text/javascript"
    src="%(portal_url)s/++resource++supersized.min.js"></script>
<script type="text/javascript"
    src="%(portal_url)s/++resource++supersized.shutter.min.js"></script>
<script type="text/javascript">
jQuery(function($){
$.supersized({
    slideshow: %(slideshow)i, // Slideshow on/off
    autoplay: %(slideshow)i,
    start_slide: 1, // Start slide (0 is random)
    slide_interval: %(speed)i,
    stop_loop: %(stop_loop)i, // Pauses slideshow on last slide
    random: 0, // Randomize slide order (Ignores start slide)
    slide_interval: %(duration)i, // Length between transitions
    // 0-None, 1-Fade, 2-Slide Top, 3-Slide Right, 4-Slide Bottom,
    // 5-Slide Left, 6-Carousel Right, 7-Carousel Left
    transition: %(transition)i,
    transition_speed: %(speed)i, // Speed of transition
    new_window: 0, // Image links open in new window/tab
    pause_hover: 0, // Pause slideshow on hover
    keyboard_nav: 1, // Keyboard navigation on/off
    // 0-Normal, 1-Hybrid speed/quality, 2-Optimizes image quality,
    // 3-Optimizes transition speed // (Only works for Firefox/IE, not Webkit)
    performance: %(performance)i,
    image_protect: 1, // Disables image dragging and right click
    // Size & Position
    min_width: %(min_width)i, // Min width allowed (in pixels)
    min_height: %(min_height)i, // Min height allowed (in pixels)
    vertical_center: %(vertical_center)i, // Vertically center background
    horizontal_center: %(horizontal_center)i, // Horizontally center background
    // Image will never exceed browser width or height (Ignores min. dim)
    fit_always: %(fit_always)i,
    // Portrait images will not exceed browser height
    fit_portrait: %(fit_portrait)i,
    // Landscape images will not exceed browser width
    fit_landscape: %(fit_landscape)i,
    // Components
    // Individual links for each slide (Options: false, 'number',
    // 'name', 'blank')
    slide_links: '%(slide_links)s',
    thumb_links: %(thumb_links)i, // Individual thumb links for each slide
    thumbnail_navigation: %(thumbnail_navigation)i, // Thumbnail navigation
    slides: %(imagelist)s,
    // Theme Options
    image_path: '++resource++supersized/',
    progress_bar: %(progress_bar)i, // Timer for each slide
    mouse_scrub: 0});
});
</script>
""" % {
        'portal_url': self.portal_url,
        'slideshow': self.settings.supersized_slideshow,
        'stop_loop': self.settings.supersized_stop_loop,
        'min_width': self.settings.supersized_min_width,
        'performance': self.settings.supersized_performance,
        'transition': self.settings.supersized_transition,
        'min_height': self.settings.supersized_min_height,
        'vertical_center': self.settings.supersized_vertical_center,
        'horizontal_center': self.settings.supersized_horizontal_center,
        'fit_always': self.settings.supersized_fit_always,
        'fit_portrait': self.settings.supersized_fit_portrait,
        'fit_landscape': self.settings.supersized_fit_landscape,
        'thumb_links': self.settings.supersized_thumb_links,
        'slide_links': self.settings.supersized_slide_links,
        'thumbnail_navigation': self.settings.supersized_thumbnail_navigation,
        'progress_bar': self.settings.supersized_progress_bar,
        'imagelist': json.dumps(imagelist),
        'speed': self.settings.duration,
        'duration': self.settings.delay,
        }
SupersizedSettings = createSettingsFactory(SupersizedDisplayType.schema)
