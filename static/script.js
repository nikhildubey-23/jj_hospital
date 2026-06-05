document.addEventListener('DOMContentLoaded', function () {
  initParticleCanvas()
  initNavbarScroll()
  initScrollAnimations()
  initCounters()
  initLightbox()
  initSmoothScroll()
})

/* ─── Particle Canvas (2D, matching React Hero) ─── */
function initParticleCanvas() {
  const canvas = document.getElementById('hero-canvas')
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  let animId, particles = []

  function resize() {
    canvas.width = window.innerWidth
    canvas.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  class Particle {
    constructor() { this.reset() }
    reset() {
      this.x = Math.random() * canvas.width
      this.y = Math.random() * canvas.height
      this.size = Math.random() * 3 + 1
      this.speedX = (Math.random() - 0.5) * 0.5
      this.speedY = (Math.random() - 0.5) * 0.5
      this.opacity = Math.random() * 0.5 + 0.2
    }
    update() {
      this.x += this.speedX
      this.y += this.speedY
      if (this.x < 0 || this.x > canvas.width) this.speedX *= -1
      if (this.y < 0 || this.y > canvas.height) this.speedY *= -1
    }
    draw() {
      ctx.beginPath()
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2)
      ctx.fillStyle = `rgba(255, 255, 255, ${this.opacity})`
      ctx.fill()
    }
  }

  for (let i = 0; i < 80; i++) particles.push(new Particle())

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    particles.forEach(p => { p.update(); p.draw() })
    animId = requestAnimationFrame(animate)
  }
  animate()

  window.addEventListener('beforeunload', () => cancelAnimationFrame(animId))
}

/* ─── Navbar Scroll Effect ─── */
function initNavbarScroll() {
  const navbar = document.getElementById('mainNavbar')
  if (!navbar) return

  function onScroll() {
    navbar.classList.toggle('scrolled', window.scrollY > 50)
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  onScroll()
}

/* ─── Scroll Animations (Intersection Observer) ─── */
function initScrollAnimations() {
  const elements = document.querySelectorAll('.anim-hidden')

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target
        const delay = parseFloat(el.getAttribute('data-delay')) || 0
        setTimeout(() => el.classList.add('anim-visible'), delay * 1000)
        observer.unobserve(el)
      }
    })
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' })

  elements.forEach(el => observer.observe(el))
}

/* ─── Counter Animation ─── */
function initCounters() {
  const counters = document.querySelectorAll('.counter')

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target
        const target = parseInt(el.getAttribute('data-target'))
        animateCounter(el, target)
        observer.unobserve(el)
      }
    })
  }, { threshold: 0.5 })

  counters.forEach(el => observer.observe(el))
}

function animateCounter(el, target) {
  const duration = 2000
  const start = performance.now()

  function update(time) {
    const progress = Math.min((time - start) / duration, 1)
    el.textContent = Math.floor(progress * target)
    if (progress < 1) requestAnimationFrame(update)
  }
  requestAnimationFrame(update)
}

/* ─── Lightbox ─── */
function openLightbox(item) {
  const img = item.querySelector('img')
  if (!img) return
  const lightbox = document.getElementById('lightbox')
  const lightboxImg = document.getElementById('lightbox-img')
  lightboxImg.src = img.src
  lightbox.style.display = 'flex'
  document.body.style.overflow = 'hidden'
}

function closeLightbox(e) {
  if (e.target !== e.currentTarget) return
  const lightbox = document.getElementById('lightbox')
  lightbox.style.display = 'none'
  document.body.style.overflow = ''
}

/* ─── Smooth Scroll for anchor links ─── */
function initSmoothScroll() {
  document.addEventListener('click', function (e) {
    const link = e.target.closest('a[href^="#"]')
    if (!link) return
    e.preventDefault()
    const id = link.getAttribute('href').slice(1)
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: 'smooth' })
  })
}
